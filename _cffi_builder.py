import cffi

ffibuilder = cffi.FFI()

ffibuilder.cdef("""
    int bytetoken_encode(
        const uint8_t *data, size_t data_len,
        int bit_width,
        uint32_t *out_indices, size_t *out_len
    );

    int bytetoken_decode(
        const uint32_t *indices, size_t num_indices,
        int bit_width,
        uint8_t *out_data, size_t *out_len
    );

    uint32_t bytetoken_crc32(const uint8_t *data, size_t len);
    size_t bytetoken_max_indices(size_t data_len, int bit_width);
    size_t bytetoken_max_bytes(size_t num_indices, int bit_width);
""")

ffibuilder.set_source("bytetoken._native", r"""
#include <stdint.h>
#include <string.h>
#include <stdlib.h>

/* --- Encode --------------------------------------------------- */

int bytetoken_encode(
    const uint8_t *data, size_t data_len,
    int bit_width,
    uint32_t *out_indices, size_t *out_len
) {
    size_t total_bits = data_len * 8;
    int pad = 0;
    if (total_bits % bit_width != 0) {
        pad = bit_width - (total_bits % bit_width);
    }
    
    size_t total_chunks = (total_bits + pad) / bit_width;
    out_indices[0] = pad;
    
    if (data_len == 0) {
        *out_len = 1;
        return pad;
    }

    size_t out_pos = 1;
    uint32_t accumulator = 0;
    int acc_bits = 0;
    size_t byte_idx = 0;
    
    while (byte_idx < data_len || acc_bits > 0) {
        while (acc_bits < bit_width && byte_idx < data_len) {
            accumulator = (accumulator << 8) | data[byte_idx];
            acc_bits += 8;
            byte_idx++;
        }
        
        if (acc_bits < bit_width && byte_idx == data_len) {
            accumulator = accumulator << (bit_width - acc_bits);
            acc_bits = bit_width;
        }
        
        out_indices[out_pos] = (accumulator >> (acc_bits - bit_width)) & ((1u << bit_width) - 1);
        acc_bits -= bit_width;
        out_pos++;
        
        accumulator &= (1u << acc_bits) - 1;
        
        if (out_pos > total_chunks) break;
    }
    
    *out_len = out_pos;
    return pad;
}

/* --- Decode --------------------------------------------------- */

int bytetoken_decode(
    const uint32_t *indices, size_t num_indices,
    int bit_width,
    uint8_t *out_data, size_t *out_len
) {
    if (num_indices <= 1) {
        *out_len = 0;
        return 0;
    }
    
    uint32_t pad = indices[0];
    size_t total_bits = (num_indices - 1) * bit_width - pad;
    size_t num_bytes = total_bits / 8;
    
    uint32_t accumulator = 0;
    int acc_bits = 0;
    size_t out_pos = 0;
    
    for (size_t i = 1; i < num_indices; i++) {
        accumulator = (accumulator << bit_width) | (indices[i] & ((1u << bit_width) - 1));
        acc_bits += bit_width;
        
        while (acc_bits >= 8 && out_pos < num_bytes) {
            acc_bits -= 8;
            out_data[out_pos] = (uint8_t)((accumulator >> acc_bits) & 0xFF);
            out_pos++;
        }
    }
    
    *out_len = out_pos;
    return 0;
}

/* --- CRC-32 -------------------------------------------------- */

static const uint32_t crc32_table[256] = {
    0x00000000, 0x77073096, 0xEE0E612C, 0x990951BA, 0x076DC419, 0x706AF48F,
    0xE963A535, 0x9E6495A3, 0x0EDB8832, 0x79DCB8A4, 0xE0D5E91B, 0x97D2D988,
    0x09B64C2B, 0x7EB17CBB, 0xE7B82D09, 0x90BF1D9F, 0x1DB71064, 0x6AB020F2,
    0xF3B97148, 0x84BE41DE, 0x1ADAD47D, 0x6DDDE4EB, 0xF4D4B551, 0x83D385C7,
    0x136C9856, 0x646BA8C0, 0xFD62F97A, 0x8A65C9EC, 0x14015C4F, 0x63066CD9,
    0xFA0F3D63, 0x8D080DF5, 0x3B6E20C8, 0x4C69105E, 0xD56041E4, 0xA2677172,
    0x3C03E4D1, 0x4B04D447, 0xD20D85FD, 0xA50AB56B, 0x35B5A8FA, 0x42B2986C,
    0xDBBBC9D6, 0xACBCF940, 0x32D86CE3, 0x45DF5C75, 0xDCD60DCF, 0xABD13D59,
    0x26D930AC, 0x51DE003A, 0xC8D75180, 0xBFD06116, 0x21B4F4B5, 0x56B3C423,
    0xCFBA9599, 0xB8BDA50F, 0x2802B89E, 0x5F058808, 0xC60CD9B2, 0xB10BE924,
    0x2F6F7C87, 0x58684C11, 0xC1611DAB, 0xB6662D3D, 0x76DC4190, 0x01DB7106,
    0x98D220BC, 0xEFD5102A, 0x71B18589, 0x06B6B51F, 0x9FBFE4A5, 0xE8B8D433,
    0x7807C9A2, 0x0F00F934, 0x9609A88E, 0xE10E9818, 0x7F6A0DBB, 0x086D3D2D,
    0x91646C97, 0xE6635C01, 0x6B6B51F4, 0x1C6C6162, 0x856530D8, 0xF262004E,
    0x6C0695ED, 0x1B01A57B, 0x8208F4C1, 0xF50FC457, 0x65B0D9C6, 0x12B7E950,
    0x8BBEB8EA, 0xFCB9887C, 0x62DD1DDF, 0x15DA2D49, 0x8CD37CF3, 0xFBD44C65,
    0x4DB26158, 0x3AB551CE, 0xA3BC0074, 0xD4BB30E2, 0x4ADFA541, 0x3DD895D7,
    0xA4D1C46D, 0xD3D6F4FB, 0x4369E96A, 0x346ED9FC, 0xAD678846, 0xDA60B8D0,
    0x44042D73, 0x33031DE5, 0xAA0A4C5F, 0xDD0D7822, 0x3AB8F2E1, 0x4DBF9F77,
    0xD4B8775D, 0xA3BF67CB, 0x34B0BCB5, 0x43B7D1F6, 0x7AF75B0A, 0x0DF0D8DF,
    0x6AF9DB7D, 0x1DFECF4B, 0x65B6ABED, 0x12B0CEEC, 0x8BEB8EAA, 0xFCEC3F1C,
    0xBFCE1E08, 0xC8D18B7E, 0x5FD0AA94, 0x28D7CB02, 0xB6B3E4A5, 0xC1B4D433,
    0x5AB0C5B9, 0x2DB7F52F, 0xB4BEA495, 0xC3B99403, 0x5CCDBBBC, 0x2BCABB2A,
    0xB2C3DABD, 0xC5C4EA2B, 0x5E08B3A6, 0x290F8330, 0xB006D28A, 0xC701E21C,
    0x596577AD, 0x2E62473B, 0xB76B1681, 0xC06C2617, 0x01000000, 0x76073096,
    0x8B08A4C3, 0xFC0F9455, 0x6506C5EF, 0x1201F579, 0x8CDA641A, 0xFBDB548C,
    0x62D40536, 0x15D335A0, 0x8AA3E4AB, 0xFDA4D43D, 0x64AD8587, 0x13AAB511,
    0x83A02C1F, 0xF4A71C89, 0x6DAE4D33, 0x1AA97DA5, 0x0909618C, 0x7E0E511A,
    0xE70700A0, 0x90003036, 0x0E04A13A, 0x790391AC, 0xE00AC016, 0x970DF080,
    0x07A2E501, 0x70A5D597, 0xE9AC842D, 0x9EABB4BB, 0x00AFA5B7, 0x77A89521,
    0xEEA1C49B, 0x99A6F40D, 0x3A03E1B9, 0x4D042D2F, 0xD40D3C95, 0xA30A0C03,
    0x33050F92, 0x44020F04, 0xDD0B38BE, 0xAA0E3E28, 0x34684A8B, 0x4367AA1D,
    0xDA61D0A7, 0xAD66E031, 0x2A600090, 0x5D6630E6, 0xC46F215C, 0xB3694BCA,
    0x2D0D2E69, 0x5A0A1EFF, 0xC3030F45, 0xB40435D3, 0x24092244, 0x530F18D2,
    0xCA062C68, 0xBD01FCFE, 0x2B667A5D, 0x5C6109CB, 0xC5680671, 0xB26F36E7,
    0xB5D0CF31, 0xC2D7BFA7, 0x5BDE7F1D, 0x2CD99E8B, 0xB2BD6B28, 0xC5BA5BBE,
    0x5CB36A04, 0x2BB45A92, 0xBBBA4D03, 0xCCBD7D95, 0x55B42E2F, 0x22B31EB9,
    0xBCF77C1A, 0xCBF04C8C, 0x52F97D36, 0x25FE4DA0, 0xD8B4E515, 0xAFB3D583
};

uint32_t bytetoken_crc32(const uint8_t *data, size_t len) {
    uint32_t crc = 0xFFFFFFFF;
    for (size_t i = 0; i < len; i++) {
        crc = crc32_table[(crc ^ data[i]) & 0xFF] ^ (crc >> 8);
    }
    return crc ^ 0xFFFFFFFF;
}

/* --- Utils --------------------------------------------------- */

size_t bytetoken_max_indices(size_t data_len, int bit_width) {
    size_t total_bits = data_len * 8;
    size_t pad = 0;
    if (total_bits % bit_width != 0) {
        pad = bit_width - (total_bits % bit_width);
    }
    return 1 + (total_bits + pad) / bit_width;  /* +1 for metadata */
}

size_t bytetoken_max_bytes(size_t num_indices, int bit_width) {
    if (num_indices <= 1) return 0;
    return ((num_indices - 1) * bit_width) / 8 + 1;
}
""", extra_compile_args=['-O3', '-march=native', '-funroll-loops'])

if __name__ == "__main__":
    ffibuilder.compile(verbose=True)
