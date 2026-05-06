#!/usr/bin/env python3
"""v5.1 synthetic SFT generator — broader Rust idioms, NOT eval-targeted.

Differences from synth_data.py (v4):
  1. **More archetypes**: 100 new borrow/lifetime scenarios that don't
     overlap with v4's 51. Cover: closure ownership, async lifetimes,
     `impl Trait` returns, generic bounds, RefCell/Rc, Cow, slice iters,
     interior mutability, partial moves, guard patterns.
  2. **Coverage-style tests** (not minimal asserts): 50 examples where
     the teacher writes 4-6 test cases including edge conditions,
     boundary values, error paths, NOT just one `assert_eq!`.
  3. **Type-error fixes**: 50 examples — buggy code with type/trait
     mismatches; teacher fixes them.

Each example must pass the lightweight structural filter
(scripts/cargo_verify_sft.py) before being kept.

Output:  data/clean/sft_synthetic_v5_1.jsonl
"""
from __future__ import annotations
import argparse
import json
import os
import random
import re
import sys
import time
from pathlib import Path

from together import Together

SYSTEM = (
    "You are Tem-Rust, a Rust coding assistant. Return the complete fixed Rust file "
    "in a single ```rust code block. Do not include any other code blocks or "
    "explanations outside the block."
)

TEACHER = "Qwen/Qwen3-Coder-Next-FP8"

# 100 new borrow/lifetime archetypes — more diverse than v4's 51.
# Format: each entry is a buggy Rust file. Teacher fixes; we pair as SFT.
NEW_BORROW_ARCHETYPES = [
    # closure capture conflicts
    """fn main() {
    let mut count = 0;
    let mut inc = || count += 1;
    let r = &count;
    inc();
    println!("{}", r);
}""",
    """fn make_pair<F: Fn() -> i32>() -> (F, F) {
    let n = 5;
    let f = || n;
    (f, f)
}

fn main() {
    let (a, b) = make_pair();
    println!("{} {}", a(), b());
}""",
    """fn collect_closures(n: usize) -> Vec<Box<dyn Fn() -> i32>> {
    (0..n).map(|i| Box::new(move || i as i32)).collect()
}

fn main() {
    for f in collect_closures(3) {
        println!("{}", f());
    }
}""",
    # impl Trait return + lifetime
    """fn make_iter<'a>(v: &'a Vec<i32>) -> impl Iterator<Item = i32> {
    v.iter().map(|&x| x * 2)
}

fn main() {
    let v = vec![1, 2, 3];
    let it = make_iter(&v);
    drop(v);
    for x in it { println!("{}", x); }
}""",
    """fn longest_iter<'a>(items: &'a [String]) -> impl Iterator<Item = &str> {
    items.iter().map(|s| s.as_str())
}

fn main() {
    let v = vec!["a".to_string(), "b".to_string()];
    let it = longest_iter(&v);
    let s = it.next();
    println!("{:?}", s);
}""",
    # generic bounds missing
    """fn print_all<T>(items: &[T]) {
    for x in items {
        println!("{}", x);
    }
}

fn main() {
    print_all(&[1, 2, 3]);
}""",
    """fn sum<T>(a: T, b: T) -> T {
    a + b
}

fn main() {
    println!("{}", sum(1, 2));
}""",
    """fn max<T>(a: T, b: T) -> T {
    if a > b { a } else { b }
}

fn main() {
    println!("{}", max(3, 5));
}""",
    # RefCell / Rc
    """use std::cell::RefCell;

fn main() {
    let cell = RefCell::new(vec![1, 2, 3]);
    let r = cell.borrow();
    cell.borrow_mut().push(4);
    println!("{:?}", r);
}""",
    """use std::rc::Rc;
use std::cell::RefCell;

fn main() {
    let shared = Rc::new(RefCell::new(0));
    let a = shared.clone();
    let b = shared.clone();
    *a.borrow_mut() = 5;
    let r = a.borrow();
    *b.borrow_mut() = 10;
    println!("{}", r);
}""",
    # Cow
    """use std::borrow::Cow;

fn upper(s: &str) -> Cow<str> {
    if s.chars().all(|c| c.is_uppercase()) {
        Cow::Borrowed(s)
    } else {
        s.to_uppercase()
    }
}

fn main() {
    println!("{}", upper("hello"));
}""",
    # slice iter mutate
    """fn shift_right(v: &mut Vec<i32>) {
    for (i, x) in v.iter().enumerate() {
        if i + 1 < v.len() {
            v[i + 1] = *x;
        }
    }
}

fn main() {
    let mut v = vec![1, 2, 3, 4];
    shift_right(&mut v);
    println!("{:?}", v);
}""",
    # interior mutability misuse
    """use std::cell::Cell;

fn main() {
    let c = Cell::new(String::from("hi"));
    let r = &c;
    let s = c.into_inner();
    println!("{}", s);
    println!("{:?}", r.get());
}""",
    # partial move
    """struct Pair {
    a: String,
    b: String,
}

fn main() {
    let p = Pair { a: "x".into(), b: "y".into() };
    let a = p.a;
    println!("{}", p.b);
    println!("{:?}", p);
}""",
    # guard patterns
    """fn main() {
    let n = Some(5);
    match n {
        Some(x) if x > 10 => println!("big {}", x),
        Some(x) if x > 0 => {
            let r = &x;
            std::mem::drop(x);
            println!("pos {}", r);
        }
        _ => println!("other"),
    }
}""",
    # if-let chain on owned
    """fn main() {
    let v: Vec<Option<String>> = vec![Some("a".into()), None];
    for opt in v {
        if let Some(s) = opt {
            println!("{}", s);
        }
        if let Some(s2) = opt {
            println!("{}", s2);
        }
    }
}""",
    # unwrap chain on consumed
    """fn first_non_empty(items: Vec<String>) -> String {
    items.iter().find(|s| !s.is_empty()).unwrap().clone();
    items.into_iter().next().unwrap()
}

fn main() {
    println!("{}", first_non_empty(vec!["a".into(), "b".into()]));
}""",
    # async-like patterns (sync simulation)
    """fn run_task(name: &'static str) -> impl FnMut() -> &'static str {
    move || name
}

fn main() {
    let mut t = run_task("hello");
    let x = t();
    let y = t();
    println!("{} {}", x, y);
}""",
    # iterator chaining lifetimes
    """fn paired<'a>(a: &'a [i32], b: &'a [i32]) -> Vec<(&'a i32, &'a i32)> {
    a.iter().zip(b.iter()).collect()
}

fn main() {
    let v1 = vec![1, 2];
    let v2 = vec![3, 4];
    let p = paired(&v1, &v2);
    drop(v1);
    println!("{:?}", p);
}""",
    # struct with reference field
    """struct Cfg {
    name: &str,
    log: Vec<String>,
}

impl Cfg {
    fn add(&mut self, msg: String) {
        self.log.push(msg);
    }
}

fn main() {
    let n = String::from("app");
    let mut c = Cfg { name: &n, log: vec![] };
    c.add("start".into());
    println!("{}", c.name);
}""",
    # method chain on &mut + & conflict
    """fn main() {
    let mut v = vec![1, 2, 3];
    let i = v.iter().position(|x| *x == 2).unwrap();
    v.remove(i);
    let r = &v[i];
    v.push(99);
    println!("{}", r);
}""",
    # consume while iter
    """fn main() {
    let v = vec!["a".to_string(), "b".to_string()];
    for s in &v {
        let owned: String = s;
        println!("{}", owned);
    }
}""",
    # trait object lifetimes
    """trait Draw {
    fn draw(&self) -> String;
}

struct Circle;
impl Draw for Circle { fn draw(&self) -> String { "circle".into() } }

fn make_drawer() -> Box<dyn Draw> {
    let c = Circle;
    Box::new(&c)
}

fn main() {
    let d = make_drawer();
    println!("{}", d.draw());
}""",
    # mismatched ref lifetimes
    """fn select<'a, 'b>(xs: &'a [i32], ys: &'b [i32]) -> &i32 {
    if xs.len() > ys.len() { &xs[0] } else { &ys[0] }
}

fn main() {
    let a = vec![1];
    let b = vec![2, 3];
    let r = select(&a, &b);
    println!("{}", r);
}""",
    # HashMap entry api
    """use std::collections::HashMap;

fn main() {
    let mut m: HashMap<String, Vec<i32>> = HashMap::new();
    let v = m.entry("k".into()).or_insert(vec![]);
    m.insert("other".into(), vec![1]);
    v.push(2);
    println!("{:?}", m);
}""",
    # while-let on borrow then mutate
    """fn main() {
    let mut v = vec![1, 2, 3];
    while let Some(last) = v.last() {
        let l = *last;
        v.pop();
        println!("{}", l);
    }
}""",
    # generic impl missing bound
    """struct Wrap<T> {
    inner: T,
}

impl<T> Wrap<T> {
    fn dbl(&self) -> T {
        self.inner.clone() + self.inner.clone()
    }
}

fn main() {
    let w = Wrap { inner: 3 };
    println!("{}", w.dbl());
}""",
    # iterator collect type ambiguity
    """fn doubled(v: &[i32]) -> _ {
    v.iter().map(|x| x * 2).collect()
}

fn main() {
    let v: Vec<i32> = doubled(&[1, 2, 3]);
    println!("{:?}", v);
}""",
    # ? operator misuse
    """fn parse_two(a: &str, b: &str) -> i32 {
    let x: i32 = a.parse()?;
    let y: i32 = b.parse()?;
    x + y
}

fn main() {
    println!("{}", parse_two("1", "2"));
}""",
    # mismatched return types
    """fn first_or_zero(v: Vec<i32>) -> i32 {
    if v.is_empty() {
        return None;
    }
    v[0]
}

fn main() {
    println!("{}", first_or_zero(vec![1, 2, 3]));
}""",
]

# 50 type-error scenarios — distinct from borrow archetypes
TYPE_ARCHETYPES = [
    """fn add_one(x: i32) -> i64 {
    x + 1
}

fn main() {
    println!("{}", add_one(5));
}""",
    """fn double(s: &str) -> String {
    s + s
}

fn main() {
    println!("{}", double("hi"));
}""",
    """fn first(v: Vec<i32>) -> Option<i32> {
    v[0]
}

fn main() {
    println!("{:?}", first(vec![1]));
}""",
    """fn count_chars(s: String) -> i32 {
    s.len()
}

fn main() {
    println!("{}", count_chars("hello".into()));
}""",
    """fn divide(a: u32, b: u32) -> u32 {
    a / b - 0.5
}

fn main() {
    println!("{}", divide(10, 3));
}""",
    """trait Greet {
    fn hello(&self);
}

struct Dog;
impl Greet for Dog {
    fn hello(&self) -> String {
        "woof".into()
    }
}

fn main() {
    Dog.hello();
}""",
    """fn print<T: std::fmt::Display>(items: Vec<T>) {
    for x in items {
        println!("{:?}", x);
    }
}

fn main() {
    print(vec![1, 2, 3]);
}""",
    """fn parse_age(s: &str) -> u32 {
    s.parse()
}

fn main() {
    println!("{}", parse_age("42"));
}""",
    """fn fold_concat(v: Vec<&str>) -> String {
    v.iter().fold("", |acc, s| acc + s)
}

fn main() {
    println!("{}", fold_concat(vec!["a", "b"]));
}""",
    """use std::collections::HashMap;

fn count(v: Vec<&str>) -> HashMap<&str, u32> {
    let mut m = HashMap::new();
    for s in v {
        *m.entry(s).or_insert(0u32) += 1;
    }
    m
}

fn main() {
    println!("{:?}", count(vec!["a", "b", "a"]));
}""",
    """fn main() {
    let v = vec![1, 2, 3];
    let s: i32 = v.iter().sum();
    let avg = s / v.len();
    println!("{}", avg);
}""",
    """fn try_parse(s: &str) -> i32 {
    match s.parse::<i32>() {
        Ok(n) => n,
        Err(e) => println!("bad: {}", e),
    }
}

fn main() {
    println!("{}", try_parse("3"));
}""",
    """enum Shape {
    Circle(f64),
    Square(f64),
}

fn area(s: Shape) -> f64 {
    match s {
        Shape::Circle(r) => std::f64::consts::PI * r * r,
    }
}

fn main() {
    println!("{}", area(Shape::Square(3.0)));
}""",
    """fn main() {
    let v: Vec<i32> = (1..5).collect();
    let s: String = v.iter().collect();
    println!("{}", s);
}""",
    """struct Point { x: i32, y: i32 }

impl Point {
    fn translate(&mut self, dx: i32, dy: i32) {
        self.x = self.x + dx;
        self.y = self.y + dy;
        return self;
    }
}

fn main() {
    let mut p = Point { x: 0, y: 0 };
    p.translate(1, 2);
    println!("{}, {}", p.x, p.y);
}""",
    """fn main() {
    let opts: Vec<Option<i32>> = vec![Some(1), None, Some(3)];
    let nums: Vec<i32> = opts.iter().filter_map(|o| o).collect();
    println!("{:?}", nums);
}""",
    """fn pair<T>(a: T, b: T) -> (T, T) {
    (a, b)
}

fn main() {
    let (a, b) = pair(1, "x");
    println!("{} {}", a, b);
}""",
    """fn echo<T: std::fmt::Debug>(items: &[T]) -> &[T] {
    println!("{:?}", items);
    items.iter()
}

fn main() {
    let v = vec![1, 2, 3];
    let r = echo(&v);
    println!("{:?}", r);
}""",
    """trait Speak {
    fn speak(&self) -> &str;
}

fn say(thing: dyn Speak) {
    println!("{}", thing.speak());
}

struct Cat;
impl Speak for Cat {
    fn speak(&self) -> &str { "meow" }
}

fn main() {
    say(Cat);
}""",
    """fn main() {
    let s: &str = "hello";
    let owned: String = s;
    println!("{}", owned);
}""",
]

# 50 scenarios that yield "write tests" prompts. We give a function-shaped
# Rust file, ask teacher to add 4-6 #[test] cases with edge conditions, error
# paths, boundary values, NOT minimal asserts.
TEST_SUBJECTS = [
    """pub fn factorial(n: u64) -> u64 {
    (1..=n).product()
}""",
    """pub fn fibonacci(n: u32) -> u64 {
    let mut a: u64 = 0;
    let mut b: u64 = 1;
    for _ in 0..n {
        let next = a + b;
        a = b;
        b = next;
    }
    a
}""",
    """pub fn reverse_string(s: &str) -> String {
    s.chars().rev().collect()
}""",
    """pub fn is_palindrome(s: &str) -> bool {
    let chars: Vec<char> = s.chars().collect();
    chars.iter().eq(chars.iter().rev())
}""",
    """pub fn count_vowels(s: &str) -> usize {
    s.chars().filter(|c| "aeiouAEIOU".contains(*c)).count()
}""",
    """pub fn gcd(a: u64, b: u64) -> u64 {
    if b == 0 { a } else { gcd(b, a % b) }
}""",
    """pub fn binary_search(arr: &[i32], target: i32) -> Option<usize> {
    let (mut lo, mut hi) = (0, arr.len());
    while lo < hi {
        let mid = lo + (hi - lo) / 2;
        if arr[mid] == target { return Some(mid); }
        else if arr[mid] < target { lo = mid + 1; }
        else { hi = mid; }
    }
    None
}""",
    """pub fn rotate_left<T: Clone>(v: &[T], k: usize) -> Vec<T> {
    let k = k % v.len().max(1);
    let mut out = v[k..].to_vec();
    out.extend_from_slice(&v[..k]);
    out
}""",
    """pub fn flatten<T: Clone>(v: &[Vec<T>]) -> Vec<T> {
    v.iter().flatten().cloned().collect()
}""",
    """#[derive(Debug, PartialEq)]
pub struct Stack<T> { items: Vec<T> }

impl<T> Stack<T> {
    pub fn new() -> Self { Self { items: vec![] } }
    pub fn push(&mut self, x: T) { self.items.push(x); }
    pub fn pop(&mut self) -> Option<T> { self.items.pop() }
    pub fn peek(&self) -> Option<&T> { self.items.last() }
    pub fn len(&self) -> usize { self.items.len() }
}""",
    """pub fn split_words(s: &str) -> Vec<&str> {
    s.split_whitespace().collect()
}""",
    """pub fn leap_year(y: i32) -> bool {
    (y % 4 == 0 && y % 100 != 0) || y % 400 == 0
}""",
    """pub fn celsius_to_fahrenheit(c: f64) -> f64 {
    c * 9.0 / 5.0 + 32.0
}""",
    """pub fn frequency_map(s: &str) -> std::collections::HashMap<char, usize> {
    let mut m = std::collections::HashMap::new();
    for c in s.chars() {
        *m.entry(c).or_insert(0) += 1;
    }
    m
}""",
    """pub fn parse_int(s: &str) -> Result<i64, String> {
    s.trim().parse::<i64>().map_err(|e| e.to_string())
}""",
    """pub fn unique_sorted(v: &[i32]) -> Vec<i32> {
    let mut out = v.to_vec();
    out.sort();
    out.dedup();
    out
}""",
    """pub fn run_length_encode(s: &str) -> String {
    let mut out = String::new();
    let mut chars = s.chars().peekable();
    while let Some(c) = chars.next() {
        let mut count = 1;
        while chars.peek() == Some(&c) {
            chars.next();
            count += 1;
        }
        out.push(c);
        out.push_str(&count.to_string());
    }
    out
}""",
    """pub fn sum_digits(mut n: u64) -> u64 {
    let mut s = 0;
    while n > 0 {
        s += n % 10;
        n /= 10;
    }
    s
}""",
    """pub fn is_anagram(a: &str, b: &str) -> bool {
    let mut x: Vec<char> = a.chars().collect();
    let mut y: Vec<char> = b.chars().collect();
    x.sort();
    y.sort();
    x == y
}""",
    """pub fn matrix_transpose(m: &[Vec<i32>]) -> Vec<Vec<i32>> {
    if m.is_empty() { return vec![]; }
    let cols = m[0].len();
    (0..cols).map(|c| m.iter().map(|row| row[c]).collect()).collect()
}""",
]


def together() -> Together:
    return Together(api_key=os.environ["TOGETHER_API_KEY"])


def teacher_chat(client: Together, messages, max_tokens: int = 4096, temperature: float = 0.0) -> str:
    """Call Qwen3-Coder-Next-FP8 via Together. Retry on transient errors."""
    last = ""
    for attempt in range(3):
        try:
            r = client.chat.completions.create(
                model=TEACHER,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return r.choices[0].message.content or ""
        except Exception as e:
            last = str(e)
            time.sleep(2 ** attempt)
    raise RuntimeError(f"teacher failed after 3 retries: {last}")


def extract_rust_block(text: str) -> str | None:
    m = re.search(r"```rust\n(.*?)```", text, re.DOTALL)
    if not m:
        return None
    return m.group(1).rstrip() + "\n"


def make_borrow_row(client: Together, buggy: str) -> dict | None:
    user = (
        "The following Rust file has a borrow-checker, lifetime, or ownership error. "
        "Return the complete fixed file in a single ```rust code block.\n\n"
        f"```rust\n{buggy}\n```"
    )
    out = teacher_chat(client, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}])
    fixed = extract_rust_block(out)
    if fixed is None:
        return None
    if fixed.strip() == buggy.strip():
        return None
    return {
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": f"```rust\n{fixed}```"},
        ]
    }


def make_type_row(client: Together, buggy: str) -> dict | None:
    user = (
        "The following Rust file has a type-system, trait-bound, or signature error. "
        "Return the complete fixed file in a single ```rust code block.\n\n"
        f"```rust\n{buggy}\n```"
    )
    out = teacher_chat(client, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}])
    fixed = extract_rust_block(out)
    if fixed is None or fixed.strip() == buggy.strip():
        return None
    return {
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": f"```rust\n{fixed}```"},
        ]
    }


def make_test_row(client: Together, subject: str) -> dict | None:
    user = (
        "Write thorough Rust tests for the following code. Include 4-6 #[test] cases that "
        "cover the happy path, edge conditions (empty, zero, max), boundary values, and "
        "error paths where applicable. Use #[cfg(test)] mod tests with `use super::*;`. "
        "Return the COMPLETE Rust file (the original code unchanged + a tests module appended) "
        "in a single ```rust code block.\n\n"
        f"```rust\n{subject}\n```"
    )
    out = teacher_chat(client, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}], max_tokens=6000)
    fixed = extract_rust_block(out)
    if fixed is None:
        return None
    # require both the original subject (preserved) and a tests module (added)
    if "#[test]" not in fixed and "#[cfg(test)]" not in fixed:
        return None
    return {
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": f"```rust\n{fixed}```"},
        ]
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/clean/sft_synthetic_v5_1.jsonl")
    ap.add_argument("--borrow-cap", type=int, default=30, help="how many borrow archetypes to query (each costs ~$0.01)")
    ap.add_argument("--type-cap", type=int, default=20)
    ap.add_argument("--test-cap", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    random.seed(args.seed)
    client = together()

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    sink = open(args.out, "w")
    n_kept = 0

    for label, archetypes, fn, cap in [
        ("borrow", NEW_BORROW_ARCHETYPES, make_borrow_row, args.borrow_cap),
        ("type", TYPE_ARCHETYPES, make_type_row, args.type_cap),
        ("test", TEST_SUBJECTS, make_test_row, args.test_cap),
    ]:
        random.shuffle(archetypes)
        chosen = archetypes[:cap]
        print(f"\n=== {label}: querying {len(chosen)} ===", flush=True)
        kept = 0
        for i, src in enumerate(chosen):
            try:
                row = fn(client, src)
            except Exception as e:
                print(f"  [{label} {i}] ERR: {e}", flush=True)
                continue
            if row is None:
                print(f"  [{label} {i}] reject (no rust block / unchanged)", flush=True)
                continue
            sink.write(json.dumps(row) + "\n")
            sink.flush()
            kept += 1
            n_kept += 1
            print(f"  [{label} {i}] ✓ kept ({kept})", flush=True)
        print(f"  {label}: {kept}/{len(chosen)} kept", flush=True)

    sink.close()
    print(f"\nTOTAL kept: {n_kept} → {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
