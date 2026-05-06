"""Generate synthetic SFT examples via teacher (Qwen3-Coder-Next-FP8) for
sub-evals where the PR-fix corpus is weak: test-writing and borrow/lifetime.

Strategy:

1. **Test-generation slice (~100 examples).**
   For each function-shaped Rust file extracted from `data/clean/sft_wholefile_v3.jsonl`'s
   *output* (the post-fix files), ask the teacher:
   "Write idiomatic #[test] cases for this Rust file. Return the complete file
    with tests appended in a single ```rust block."
   Use teacher's output as the SFT target, paired with the same input file.

2. **Borrow/lifetime slice (~50 examples).**
   Hand-curated set of buggy-Rust archetypes (move-after-borrow, lifetime
   missing, &mut/& conflict, etc.). For each, ask teacher to write a fix.
   Use teacher's fix as SFT target.

Both slices use the same SFT format as v2/v3 (whole-file completion in a
rust code block, system + user + assistant).
"""
from __future__ import annotations
import json
import os
import re
import sys
import time
from pathlib import Path

from together import Together


SYSTEM = (
    "You are Tem-Rust, a Rust coding assistant. Return the complete Rust file "
    "in a single ```rust code block. Do not include any other code blocks or "
    "explanations outside the block."
)

TEACHER = "Qwen/Qwen3-Coder-Next-FP8"

# 50 hand-curated buggy-Rust archetypes (small canonical examples). Teacher
# fixes them; we pair the broken input with teacher's fix as SFT.
BORROW_ARCHETYPES = [
    # move-after-borrow
    """fn main() {
    let s = String::from("hello");
    let r = &s;
    let s2 = s;
    println!("{}", r);
}""",
    """fn print_first(items: Vec<String>) {
    let f = &items[0];
    drop(items);
    println!("{}", f);
}

fn main() {
    print_first(vec!["a".into(), "b".into()]);
}""",
    """fn main() {
    let mut v = vec![1, 2, 3];
    let r = &v[0];
    v.push(4);
    println!("{}", r);
}""",
    # lifetime missing
    """fn longest(x: &str, y: &str) -> &str {
    if x.len() > y.len() { x } else { y }
}

fn main() {
    let a = String::from("long string");
    let b = String::from("short");
    let r = longest(&a, &b);
    println!("{}", r);
}""",
    """struct Holder {
    name: &str,
}

fn main() {
    let s = String::from("Alice");
    let h = Holder { name: &s };
    println!("{}", h.name);
}""",
    """fn first_word(s: &String) -> &str {
    s.split_whitespace().next().unwrap_or("")
}

fn returns_first() -> &str {
    let s = String::from("hello world");
    first_word(&s)
}

fn main() {
    println!("{}", returns_first());
}""",
    # &mut / & conflict
    """fn main() {
    let mut v = vec![1, 2, 3];
    let r1 = &v;
    let r2 = &mut v;
    r2.push(4);
    println!("{:?}", r1);
}""",
    """fn double_first(v: &mut Vec<i32>) {
    let f = &v[0];
    v.push(*f * 2);
}

fn main() {
    let mut v = vec![1, 2, 3];
    double_first(&mut v);
    println!("{:?}", v);
}""",
    # iterator-consumes-vec
    """fn longest_len(items: Vec<String>) -> usize {
    let mut longest = &items[0];
    for item in items {
        if item.len() > longest.len() {
            longest = &item;
        }
    }
    longest.len()
}

fn main() {
    let v = vec![String::from("a"), String::from("bb")];
    println!("{}", longest_len(v));
}""",
    """fn sum_strings(items: Vec<String>) -> usize {
    let mut total = 0;
    for s in items {
        total += s.len();
    }
    println!("{:?}", items);
    total
}

fn main() {
    println!("{}", sum_strings(vec!["a".into(), "bb".into()]));
}""",
    # closure capture
    """fn main() {
    let s = String::from("hello");
    let f = move || println!("{}", s);
    f();
    println!("{}", s);
}""",
    """fn make_counter() -> impl FnMut() -> i32 {
    let mut n = 0;
    || { n += 1; n }
}

fn main() {
    let mut c = make_counter();
    println!("{}", c());
}""",
    # dangling reference
    """fn dangle() -> &String {
    let s = String::from("hello");
    &s
}

fn main() {
    let r = dangle();
    println!("{}", r);
}""",
    """fn make_pair() -> (&str, &str) {
    let a = String::from("a");
    let b = String::from("b");
    (&a, &b)
}

fn main() {
    let (x, y) = make_pair();
    println!("{} {}", x, y);
}""",
    # ownership in struct
    """struct Wrapper {
    inner: String,
}

fn unwrap(w: Wrapper) -> &str {
    &w.inner
}

fn main() {
    let w = Wrapper { inner: "hi".into() };
    let s = unwrap(w);
    println!("{}", s);
}""",
    # iter().collect() lifetime
    """fn collect_refs<'a>(items: &'a [String]) -> Vec<&str> {
    items.iter().map(|s| s.as_str()).collect()
}

fn main() {
    let v = vec!["a".to_string(), "b".to_string()];
    let refs = collect_refs(&v);
    drop(v);
    println!("{:?}", refs);
}""",
    # match with binding
    """fn main() {
    let s = Some(String::from("value"));
    match &s {
        Some(v) => {
            let owned: String = v;
            println!("{}", owned);
        }
        None => {}
    }
}""",
    # static lifetime elision
    """fn first_static(s: &str) -> &'static str {
    let result = s.to_owned();
    &result
}

fn main() {
    let r = first_static("hello");
    println!("{}", r);
}""",
    # while-let on owned
    """fn main() {
    let v = vec![1, 2, 3];
    while let Some(x) = v.pop() {
        println!("{}", x);
    }
}""",
    # Box dereference
    """fn main() {
    let b = Box::new(5);
    let r = &b;
    let n = *b;
    println!("{} {}", r, n);
}""",
    # Vec::iter while pushing
    """fn main() {
    let mut v = vec![1, 2, 3];
    for x in v.iter() {
        v.push(*x);
    }
    println!("{:?}", v);
}""",
    # HashMap entry vs get_mut
    """use std::collections::HashMap;
fn main() {
    let mut m = HashMap::new();
    m.insert("a", 1);
    let v = m.get(&"a").unwrap();
    m.insert("b", 2);
    println!("{}", v);
}""",
    # &mut self method chain
    """struct Builder { items: Vec<i32> }
impl Builder {
    fn add(&mut self, x: i32) -> &mut Self { self.items.push(x); self }
}
fn main() {
    let mut b = Builder { items: vec![] };
    let chained = b.add(1).add(2);
    let other = b.add(3);
    println!("{:?}", chained.items);
}""",
    # multiple immutable borrows OK
    """fn main() {
    let mut v = vec![1, 2, 3];
    let r1 = &v[0];
    v.clear();
    println!("{}", r1);
}""",
    # PhantomData lifetime
    """struct Slice<T> { data: *const T, len: usize }
impl<T> Slice<T> {
    fn first(&self) -> &T {
        unsafe { &*self.data }
    }
}
fn main() {
    let v = vec![1, 2, 3];
    let s = Slice { data: v.as_ptr(), len: v.len() };
    drop(v);
    println!("{}", s.first());
}""",
    # impl trait and lifetimes
    """fn make_iter(v: Vec<i32>) -> impl Iterator<Item = &i32> {
    v.iter()
}
fn main() {
    let it = make_iter(vec![1,2,3]);
    for x in it { println!("{}", x); }
}""",
    # iter_mut while reading
    """fn main() {
    let mut v = vec![1, 2, 3];
    let r = &v;
    for x in v.iter_mut() {
        *x += 1;
    }
    println!("{:?}", r);
}""",
    # Rc<RefCell> misuse
    """use std::cell::RefCell;
fn main() {
    let c = RefCell::new(vec![1,2,3]);
    let r1 = c.borrow();
    let r2 = c.borrow_mut();
    println!("{} {}", r1.len(), r2.len());
}""",
    # async closure capture
    """async fn double(v: Vec<i32>) -> Vec<i32> {
    v.iter().map(|x| x * 2).collect()
}
async fn run() {
    let v = vec![1,2,3];
    let f = double(v);
    println!("{}", v.len());
    f.await;
}
fn main() {}""",
    # str slicing past unicode boundary
    """fn first_char(s: &str) -> &str {
    &s[0..1]
}
fn main() {
    let s = "café";
    let first = first_char(s);
    let next = first_char(&s[1..]);
    println!("{} {}", first, next);
}""",
    # if-let-else with move
    """fn main() {
    let opt: Option<String> = Some("hi".into());
    if let Some(s) = opt {
        println!("{}", s);
    }
    println!("{:?}", opt);
}""",
    # Vec<String> sort by &str
    """fn main() {
    let mut v = vec!["b".to_string(), "a".to_string()];
    v.sort_by(|a, b| {
        let ar = a.as_str();
        let br = b.as_str();
        ar.cmp(br)
    });
    println!("{:?}", v);
}""",
    # generic over reference
    """fn print_all<T>(items: T) where T: IntoIterator<Item = &str> {
    for s in items { println!("{}", s); }
}
fn main() {
    let v = vec!["a", "b"];
    print_all(v);
}""",
    # struct with self-referential
    """struct Doc {
    text: String,
    title: &str,
}
fn main() {
    let d = Doc {
        text: "Hello world".to_string(),
        title: &"Hello world"[0..5],
    };
    println!("{}", d.title);
}""",
    # method returning slice from owned
    """struct Buffer { data: Vec<u8> }
impl Buffer {
    fn first_byte(self) -> &u8 {
        &self.data[0]
    }
}
fn main() {
    let b = Buffer { data: vec![1,2,3] };
    let r = b.first_byte();
    println!("{}", r);
}""",
    # passing &mut to closure twice
    """fn main() {
    let mut v = vec![1,2,3];
    let mut closure = || v.push(4);
    closure();
    println!("{:?}", v);
    closure();
}""",
    # Rc clone vs reference
    """use std::rc::Rc;
fn main() {
    let r = Rc::new(vec![1,2,3]);
    let a = &r;
    let b = Rc::clone(&r);
    drop(r);
    println!("{:?} {:?}", a, b);
}""",
    # iterator chain consuming
    """fn main() {
    let v = vec!["a".to_string(), "b".to_string()];
    let lengths: Vec<usize> = v.iter().map(|s| s.len()).collect();
    drop(v);
    let total: usize = lengths.iter().sum();
    let first = &v[0];
    println!("{} {}", total, first);
}""",
    # method on owned then borrow
    """fn main() {
    let s = String::from("hello world");
    let len = s.len();
    drop(s);
    let upper = s.to_uppercase();
    println!("{} {}", len, upper);
}""",
    # unsafe pointer outliving
    """fn make_ptr() -> *const i32 {
    let n = 42;
    &n as *const i32
}
fn main() {
    let p = make_ptr();
    unsafe { println!("{}", *p); }
}""",
    # generic associated lifetime
    """trait Container {
    type Item;
    fn get(&self, i: usize) -> &Self::Item;
}
struct V(Vec<i32>);
impl Container for V {
    type Item = i32;
    fn get(&self, i: usize) -> &i32 {
        let v = &self.0[i];
        drop(self);
        v
    }
}
fn main() {}""",
    # vec drain inside iter
    """fn main() {
    let mut v = vec![1,2,3,4];
    for x in v.iter() {
        if *x == 2 {
            v.drain(..);
        }
    }
    println!("{:?}", v);
}""",
    # split_at_mut
    """fn main() {
    let mut v = vec![1,2,3,4];
    let (a, b) = v.split_at(2);
    let am = &mut v[0];
    *am = 9;
    println!("{:?} {:?}", a, b);
}""",
    # &Vec<T> vs &[T]
    """fn first(v: &Vec<i32>) -> i32 { v[0] }
fn main() {
    let v = vec![1,2,3];
    let f = first(&v);
    let m = &mut v;
    m.push(4);
    println!("{} {:?}", f, m);
}""",
    # closure FnOnce on captured
    """fn run<F: Fn()>(f: F) { f(); f(); }
fn main() {
    let s = String::from("hi");
    run(move || println!("{}", s));
}""",
    # type mismatch between &str/String
    """fn welcome(name: &String) -> String {
    format!("Hello, {}", name)
}
fn main() {
    let s = "world";
    let msg = welcome(s);
    println!("{}", msg);
}""",
    # trait object lifetime
    """trait Speak { fn speak(&self) -> &str; }
impl Speak for String { fn speak(&self) -> &str { self.as_str() } }
fn boxed() -> Box<dyn Speak> {
    let s = String::from("hello");
    Box::new(s)
}
fn main() {
    let b = boxed();
    println!("{}", b.speak());
}""",
    # if let Some(&x)
    """fn main() {
    let opt: Option<String> = Some("hi".into());
    if let Some(s) = &opt {
        let owned: String = s;
        println!("{}", owned);
    }
}""",
    # Vec<&str> from String
    """fn collect_words() -> Vec<&str> {
    let s = String::from("hello world");
    s.split_whitespace().collect()
}
fn main() {
    println!("{:?}", collect_words());
}""",
    # &mut through Box
    """fn main() {
    let mut b = Box::new(vec![1,2,3]);
    let r1 = &b;
    let r2 = &mut b;
    r2.push(4);
    println!("{:?} {:?}", r1, r2);
}""",
    # ownership of return inside loop
    """fn main() {
    let mut owners: Vec<String> = vec![];
    for i in 0..3 {
        let s = format!("item-{}", i);
        owners.push(s);
        println!("just pushed: {}", s);
    }
    println!("{:?}", owners);
}""",
]


def teacher_complete(client: Together, system: str, user: str, max_tokens: int = 4000) -> str | None:
    """One-shot teacher call. Returns the assistant text or None on failure."""
    try:
        r = client.chat.completions.create(
            model=TEACHER,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=0.2,
        )
        return r.choices[0].message.content
    except Exception as e:
        print(f"  teacher error: {e}", file=sys.stderr)
        return None


def extract_rust_block(text: str) -> str | None:
    m = re.search(r"```(?:rust)?\s*\n(.*?)\n```", text, re.DOTALL)
    return m.group(1) if m else None


def gen_test_examples(client: Together, max_n: int, sink) -> list[dict]:
    """For each post-fix file in v3 SFT, ask teacher to write tests.

    Flushes each accepted row to `sink` immediately so a kill mid-run preserves
    progress."""
    out: list[dict] = []
    src_path = Path("data/clean/sft_wholefile_v3.jsonl")
    if not src_path.exists():
        return out
    seen_files = set()
    with src_path.open() as f:
        for line in f:
            if not line.strip() or len(out) >= max_n:
                continue
            d = json.loads(line)
            assistant = d["messages"][-1]["content"]
            code = extract_rust_block(assistant)
            if not code or not (200 < len(code) < 6000):
                continue
            if "fn " not in code or "#[test]" in code:
                continue
            sig = code[:100]
            if sig in seen_files:
                continue
            seen_files.add(sig)
            user = (
                f"Here's a Rust file. Add 3-5 idiomatic `#[test]` functions inside a "
                f"`#[cfg(test)] mod tests {{ ... }}` block at the bottom that exercise "
                f"the public functions. Keep the existing code unchanged. Return the "
                f"complete file in a single ```rust code block.\n\n```rust\n{code}\n```"
            )
            ans = teacher_complete(client, SYSTEM, user, max_tokens=2500)
            if not ans:
                continue
            ans_code = extract_rust_block(ans)
            if not ans_code or "#[test]" not in ans_code:
                continue
            sft_user = (
                f"Add idiomatic test cases for the public functions in this Rust file. "
                f"Wrap them in `#[cfg(test)] mod tests {{ ... }}`. Return the complete "
                f"file in a single ```rust code block.\n\n```rust\n{code}\n```"
            )
            row = {
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": sft_user},
                    {"role": "assistant", "content": f"```rust\n{ans_code}\n```"},
                ]
            }
            out.append(row)
            sink.write(json.dumps(row, ensure_ascii=False) + "\n")
            sink.flush()
            print(f"  test examples: {len(out)}/{max_n}", flush=True)
            time.sleep(0.3)
    return out


def gen_borrow_examples(client: Together, sink) -> list[dict]:
    """For each broken archetype, ask teacher for the fixed version. Flushes each row."""
    out: list[dict] = []
    for i, broken in enumerate(BORROW_ARCHETYPES):
        user = (
            f"Fix the Rust borrow-checker / lifetime / type error(s) in this code. "
            f"Preserve the original logic and `fn main` behavior. Return the complete "
            f"corrected program in a single ```rust code block.\n\n```rust\n{broken}\n```"
        )
        ans = teacher_complete(client, SYSTEM, user, max_tokens=2000)
        if not ans:
            continue
        ans_code = extract_rust_block(ans)
        if not ans_code:
            continue
        sft_user = (
            f"Fix the borrow-checker / lifetime / type error(s) in this Rust code. "
            f"Preserve the original behavior. Return the complete corrected program "
            f"in a single ```rust code block.\n\n```rust\n{broken}\n```"
        )
        row = {
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": sft_user},
                {"role": "assistant", "content": f"```rust\n{ans_code}\n```"},
            ]
        }
        out.append(row)
        sink.write(json.dumps(row, ensure_ascii=False) + "\n")
        sink.flush()
        print(f"  borrow examples: {len(out)}/{len(BORROW_ARCHETYPES)}", flush=True)
        time.sleep(0.3)
    return out


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-cap", type=int, default=50, help="Max test-generation examples")
    ap.add_argument("--out", default="data/clean/sft_synthetic.jsonl")
    args = ap.parse_args()

    client = Together(api_key=os.environ["TOGETHER_API_KEY"])
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w") as sink:
        print("=== test-generation slice ===", flush=True)
        test_rows = gen_test_examples(client, max_n=args.test_cap, sink=sink)
        print(f"  wrote {len(test_rows)} test examples", flush=True)

        print(flush=True)
        print("=== borrow/lifetime slice ===", flush=True)
        borrow_rows = gen_borrow_examples(client, sink=sink)
        print(f"  wrote {len(borrow_rows)} borrow examples", flush=True)

    print(f"\nTotal: {len(test_rows) + len(borrow_rows)} synthetic examples → {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
