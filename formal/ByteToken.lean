/-
ByteToken formalization skeleton
================================

Status: work in progress.

This file intentionally does NOT claim a machine-checked proof of concrete BPE
or tiktoken behavior. The repository currently formalizes only the shape of the
fixed-alphabet model. Tokenizer semantics and concatenation safety must be
modeled and proved separately before this directory can be described as formal
verification of the protocol.
-/

import Mathlib.Data.Nat.Basic

abbrev Token := Nat

structure FixedAlphabetModel where
  alphabetSize : Nat
  bitWidth : Nat
  capacity : 2 ^ bitWidth ≤ alphabetSize

structure EncodedSymbol (m : FixedAlphabetModel) where
  value : Nat
  inRange : value < 2 ^ m.bitWidth

/-!
The next milestone is a concrete tokenizer semantics and a machine-checkable
definition of sequence-level concatenation safety. Until then, tokenizer scans
in the Python implementation are empirical results rather than Lean theorems.
-/
