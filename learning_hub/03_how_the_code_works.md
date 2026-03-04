# 💻 Guide 3: Code Architecture

In this guide, we dive deep into the two-language architecture (Python and Rust) that makes ByteToken both developer-friendly and incredibly fast.

---

### 👶 The Simple Version (For Beginners)

#### The Two-Story Building 

Think of our code like a two-story building:

**🏠 The Second Floor: The Python API (`core.py`)**  
This is the nice, air-conditioned office where the Boss sits. If you are a programmer who wants to use ByteToken, you talk to the Boss. You say, "Hey Python Boss, here is a big sentence: `Hello World!`. Please turn it into tokens." The Python Boss says, "Sure thing!" and sends it downstairs.

**🏭 The First Floor: The Rust Engine (`native_build.py` / `src/`)**  
This is the loud, incredibly fast factory floor. When the Boss sends down the sentence `Hello World!`, the Rust Engine goes to work. It chops up the letters instantly using super-fast math. 

Remember the Zero-Copy Teleporter we talked about in Guide 2? As soon as the Rust Engine has the tokens `[15496, 2159, 2]`, it places them in the Teleporter, and *Poof*, they are back on the Boss's desk!

#### How Do We Train the Engine? 

A factory needs instructions. The AI doesn't just guess what Tokens to make. It uses a **Vocabulary**. A Vocabulary is like a massive dictionary that says:
- "Hel" = Token 500
- "lo" = Token 23
- " World" = Token 999

Before the Rust Engine can do its fast chopping, it has to load this gigantic dictionary into its brain. So, when you look at our code, you’ll see pieces that exist just to load up that dictionary once. After that, it stays running super fast for hours!

---

### 🎓 The Deep Dive (For Engineers & Researchers)

#### The FFI Boundary Design Strategy

The goal is to maintain the semantic ease of Python while delegating the $O(N)$ text scanning to a compiled language. Our high-level abstraction (`bytetoken/core.py`) is written in pure Python. It acts as an adapter, handling file I/O operations, text encoding, sanity checks, and class initialization before handing execution over to the native layer.

By insulating the user from the C-API boundary, if a developer fails to compile the Rust codebase, the Python interface can gracefully degrade or throw explicit missing-DLL errors rather than failing with a raw memory segfault.

#### Rust Vocabulary Data Structures

Tokenizing arbitrary byte streams or utf-8 text efficiently (`O(N)` linear time or better) requires sophisticated substring matching. 

A naive iteration checking against a 32,000-key dictionary results in catastrophic algorithmic degradation ($O(N \cdot M)$ where $M$ is vocab size).

Instead, the Rust native engine constructs an optimized **Trie** (Prefix Tree) or an **Aho-Corasick Automaton**. 
When the Rust object is instantiated:
1. It reads the raw JSON vocabulary file into memory.
2. It compiles the key-value mappings into an automaton state machine.
3. This state machine is held in native process memory, persisting across multiple Python calls via the PyO3 class macro (`#[pyclass]`).

When `encode(text)` is invoked, the Rust code scans the utf-8 characters using a single, algorithmic linear traversal of the automaton, generating the token IDs seamlessly without garbage collection stutters.
