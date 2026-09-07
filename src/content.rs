// Rust Academy — static course content (lessons, quizzes, cheat sheet,
// achievements and Code Lab scenarios).

use crate::{
    Achievement, Block, CheatEntry, CodeLine, DayBar, LessonInfo, ModuleInfo, QuizQ,
};

fn line(no: i32, block: i32, text: &str, color: i32) -> CodeLine {
    CodeLine {
        no,
        block,
        text: text.into(),
        color,
    }
}

fn lesson(
    id: i32,
    module: i32,
    icon: &str,
    title: &str,
    subtitle: &str,
    duration: &str,
    xp: &str,
    status: i32,
    progress: f32,
) -> LessonInfo {
    LessonInfo {
        id,
        module,
        icon: icon.into(),
        title: title.into(),
        subtitle: subtitle.into(),
        duration: duration.into(),
        xp: xp.into(),
        best: String::new().into(),
        status,
        progress,
    }
}

pub fn modules() -> Vec<ModuleInfo> {
    vec![
        ModuleInfo {
            id: 1,
            icon: "spark".into(),
            title: "Getting Started".into(),
            desc: "Write your first Rust program and learn the language fundamentals.".into(),
            done: 0,
            total: 4,
        },
        ModuleInfo {
            id: 2,
            icon: "shield".into(),
            title: "Ownership & Memory".into(),
            desc: "Understand the heart of Rust: ownership, borrowing and lifetimes.".into(),
            done: 0,
            total: 3,
        },
        ModuleInfo {
            id: 3,
            icon: "gear".into(),
            title: "Real-World Rust".into(),
            desc: "Structs, enums, traits, closures and errors — build with confidence.".into(),
            done: 0,
            total: 3,
        },
    ]
}

pub fn lessons() -> Vec<LessonInfo> {
    vec![
        lesson(1, 1, "terminal", "Hello, Rust!", "Write, compile and run your first program.", "8", "40", 2, 1.0),
        lesson(2, 1, "cube", "Variables & Mutability", "let, mut, shadows and constants.", "10", "50", 1, 0.35),
        lesson(3, 1, "layers", "Data Types", "Integers, floats, bools, chars and tuples.", "12", "60", 0, 0.0),
        lesson(4, 1, "flag", "Control Flow", "if, match and loops — the Rust way.", "14", "70", 0, 0.0),
        lesson(5, 2, "shield", "Ownership Basics", "Why Rust has no garbage collector.", "12", "70", 0, 0.0),
        lesson(6, 2, "link", "Borrowing & References", "Borrow rules that prevent data races.", "14", "80", 0, 0.0),
        lesson(7, 2, "cube", "Strings & Slices", "String, &str, slices and indexing.", "12", "70", 0, 0.0),
        lesson(8, 3, "puzzle", "Structs & Enums", "Model your data with structs and enums.", "14", "80", 0, 0.0),
        lesson(9, 3, "star", "Traits & Generics", "Write reusable, polymorphic code.", "16", "90", 0, 0.0),
        lesson(10, 3, "warn", "Error Handling", "Result, Option and the ? operator.", "14", "80", 0, 0.0),
    ]
}

// ---------------------------------------------------------------------------
// Per-lesson content
// ---------------------------------------------------------------------------

fn code_lines_lesson(id: i32) -> Vec<CodeLine> {
    match id {
        1 => vec![
            line(1, 2, "fn main() {", 1),
            line(2, 2, "    println!(\"Hello, Rust!\");", 2),
            line(3, 2, "    let x = 42; // a magic number", 3),
            line(4, 2, "    println!(\"x is {}\", x);", 2),
            line(5, 2, "}", 1),
        ],
        2 => vec![
            line(1, 2, "fn main() {", 1),
            line(2, 2, "    let x = 5;        // immutable", 0),
            line(3, 2, "    let mut y = 10;   // mutable", 1),
            line(4, 2, "    y += x;           // allowed: y is mut", 0),
            line(5, 2, "    println!(\"{}\", y);", 2),
            line(6, 2, "}", 1),
        ],
        3 => vec![
            line(1, 2, "fn main() {", 1),
            line(2, 2, "    let score: i32 = 99;", 5),
            line(3, 2, "    let pi: f64 = 3.1415;", 5),
            line(4, 2, "    let done: bool = true;", 5),
            line(5, 2, "    let letter: char = 'R';", 5),
            line(6, 2, "    let pair: (i32, &str) = (7, \"lucky\");", 5),
            line(7, 2, "    4", 4),
            line(8, 2, "}", 1),
        ],
        4 => vec![
            line(1, 2, "fn main() {", 1),
            line(2, 2, "    for n in 1..=5 {", 1),
            line(3, 2, "        match n % 2 {", 1),
            line(4, 2, "            0 => println!(\"even\"),", 2),
            line(5, 2, "            _ => println!(\"odd\"),", 2),
            line(6, 2, "        }", 1),
            line(7, 2, "    }", 1),
            line(8, 2, "}", 1),
        ],
        5 => vec![
            line(1, 2, "fn main() {", 1),
            line(2, 2, "    let s1 = String::from(\"hello\");", 0),
            line(3, 2, "    let s2 = s1; // s1 is moved, no longer valid", 2),
            line(4, 2, "    println!(\"{}\", s2);", 2),
            line(5, 2, "    // println!(\"{}\", s1); // compile error!", 3),
            line(6, 2, "}", 1),
        ],
        6 => vec![
            line(1, 2, "fn main() {", 1),
            line(2, 2, "    let mut s = String::from(\"rust\");", 0),
            line(3, 2, "    let r1 = &s;      // shared borrow", 5),
            line(4, 2, "    let r2 = &s;      // more shared borrows are fine", 5),
            line(5, 2, "    println!(\"{} {}\", r1, r2);", 2),
            line(6, 2, "    let m = &mut s;   // exclusive borrow", 6),
            line(7, 2, "    m.push_str(\" forever\");", 2),
            line(8, 2, "}", 1),
        ],
        7 => vec![
            line(1, 2, "fn main() {", 1),
            line(2, 2, "    let s = String::from(\"hello world\");", 0),
            line(3, 2, "    let word = &s[0..5]; // a slice", 5),
            line(4, 2, "    println!(\"{}\", word);", 2),
            line(5, 2, "    let bytes = s.as_bytes();", 0),
            line(6, 2, "}", 1),
        ],
        8 => vec![
            line(1, 2, "struct Point { x: i32, y: i32 }", 5),
            line(2, 2, "", 0),
            line(3, 2, "enum Color { Red, Green, Blue }", 5),
            line(4, 2, "", 0),
            line(5, 2, "fn main() {", 1),
            line(6, 2, "    let p = Point { x: 10, y: 20 };", 0),
            line(7, 2, "    let c = Color::Green;", 0),
            line(8, 2, "    println!(\"({},{}) {:?}\", p.x, p.y, c);", 2),
            line(9, 2, "}", 1),
        ],
        9 => vec![
            line(1, 2, "trait Area {", 1),
            line(2, 2, "    fn area(&self) -> f64;", 6),
            line(3, 2, "}", 1),
            line(4, 2, "", 0),
            line(5, 2, "struct Circle { r: f64 }", 5),
            line(6, 2, "impl Area for Circle {", 1),
            line(7, 2, "    fn area(&self) -> f64 { 3.14 * self.r * self.r }", 0),
            line(8, 2, "}", 1),
        ],
        10 => vec![
            line(1, 2, "use std::fs;", 7),
            line(2, 2, "", 0),
            line(3, 2, "fn read_config() -> Result<String, std::io::Error> {", 1),
            line(4, 2, "    fs::read_to_string(\"config.toml\")", 0),
            line(5, 2, "}", 1),
            line(6, 2, "", 0),
            line(7, 2, "fn main() {", 1),
            line(8, 2, "    match read_config() {", 1),
            line(9, 2, "        Ok(c) => println!(\"{}\", c),", 2),
            line(10, 2, "        Err(e) => eprintln!(\"failed: {}\", e),", 2),
            line(11, 2, "    }", 1),
            line(12, 2, "}", 1),
        ],
        _ => Vec::new(),
    }
}

fn blocks_lesson(id: i32) -> Vec<Block> {
    let b = |id: i32, kind: i32, title: &str, text: &str, file: &str| Block {
        id,
        kind,
        title: title.into(),
        text: text.into(),
        file: file.into(),
    };
    match id {
        1 => vec![
            b(0, 0, "Welcome to Rust!", "", ""),
            b(1, 1, "Rust is a systems language that gives you blazing performance with memory safety. Your first step is a tiny program that prints a greeting.", "", ""),
            b(2, 2, "", "", "main.rs"),
            b(3, 1, "The `fn main()` function is the entry point of every Rust binary. `println!` is a macro (note the `!`) that prints a line of text.", "", ""),
            b(4, 3, "Try it", "Change the string inside println! and run the program again. The `{}` placeholder is filled by the next argument.", ""),
        ],
        2 => vec![
            b(0, 0, "Variables & Mutability", "", ""),
            b(1, 1, "Variables are immutable by default in Rust. Use `let` for a binding and add `mut` when the value must change. Shadowing lets you re-use a name with a new value.", "", ""),
            b(2, 2, "", "", "main.rs"),
            b(3, 1, "Notice that `x` never changes — trying `x += 1` would be a compile error. That safety is a feature, not a limitation.", "", ""),
            b(4, 4, "Gotcha", "`let x = 5; let x = x + 1;` is shadowing, not mutation — the old value is still valid until the end of the scope.", ""),
        ],
        3 => vec![
            b(0, 0, "Data Types", "", ""),
            b(1, 1, "Rust is statically typed, but the compiler infers most types for you. Signed integers are `i8`–`i128`, unsigned are `u8`–`u128`; floats are `f32` and `f64`.", "", ""),
            b(2, 2, "", "", "main.rs"),
            b(3, 3, "Tip", "When a number matters, annotate the type explicitly (`let n: u64 = 42;`) so the compiler doesn't guess.", ""),
        ],
        4 => vec![
            b(0, 0, "Control Flow", "", ""),
            b(1, 1, "`if` is an expression in Rust, and `match` is a powerful switch that must cover every case. `for` loops over iterators; `while` and `loop` cover the rest.", "", ""),
            b(2, 2, "", "", "main.rs"),
            b(3, 3, "Tip", "A match arm `_ =>` is the catch-all. Rust will refuse to compile your code until every possibility is handled.", ""),
        ],
        5 => vec![
            b(0, 0, "Ownership Basics", "", ""),
            b(1, 1, "Every value in Rust has exactly one owner. When the owner goes out of scope, the value is dropped — automatically, without a garbage collector.", "", ""),
            b(2, 2, "", "", "main.rs"),
            b(3, 1, "Assigning `s1` to `s2` *moves* the String. The old binding is no longer usable, which prevents double-frees and use-after-free bugs.", "", ""),
            b(4, 4, "Warning", "This is why Rust can be memory-safe without a runtime: ownership is checked entirely at compile time.", ""),
        ],
        6 => vec![
            b(0, 0, "Borrowing & References", "", ""),
            b(1, 1, "Instead of moving a value, you can lend it: `&x` borrows read-only, `&mut x` borrows for writing. Rust enforces the rules at compile time.", "", ""),
            b(2, 2, "", "", "main.rs"),
            b(3, 1, "The key rule: you can have many shared borrows, or exactly one mutable borrow — never both at the same time.", "", ""),
            b(4, 4, "Warning", "Borrowed data must not outlive its owner. The compiler tracks this with lifetimes and rejects dangling references.", ""),
        ],
        7 => vec![
            b(0, 0, "Strings & Slices", "", ""),
            b(1, 1, "`String` owns its characters; `&str` is a reference to a string. Slices like `&s[0..5]` borrow a part of a collection without copying.", "", ""),
            b(2, 2, "", "", "main.rs"),
            b(3, 3, "Tip", "Use `&str` for parameters when you only need to read; use `String` when you need to own or mutate the text.", ""),
        ],
        8 => vec![
            b(0, 0, "Structs & Enums", "", ""),
            b(1, 1, "`struct` groups related data together. `enum` describes a value that can be one of several variants — the basis of Rust's algebraic data types.", "", ""),
            b(2, 2, "", "", "main.rs"),
            b(3, 3, "Tip", "Derive `Debug` (and `Clone`, `PartialEq`, ...) with `#[derive(...)]` to get common implementations for free.", ""),
        ],
        9 => vec![
            b(0, 0, "Traits & Generics", "", ""),
            b(1, 1, "A trait defines behavior that types can implement. Generics let one function work with many types while keeping full type safety and zero runtime cost.", "", ""),
            b(2, 2, "", "", "main.rs"),
            b(3, 3, "Tip", "`impl Trait for Type` can be implemented in your crate or with `impl` blocks for foreign types when allowed by the orphan rule.", ""),
        ],
        10 => vec![
            b(0, 0, "Error Handling", "", ""),
            b(1, 1, "Rust has no exceptions. Fallible functions return `Result<T, E>`; the `?` operator propagates errors to the caller concisely.", "", ""),
            b(2, 2, "", "", "main.rs"),
            b(3, 4, "Warning", "Never `unwrap()` or `expect()` in production paths you can't prove — a panic aborts the process. Match on the Result or propagate with `?`.", ""),
        ],
        _ => Vec::new(),
    }
}

fn q(
    text: &str,
    a: &str,
    b: &str,
    c: &str,
    d: &str,
    answer: i32,
    why: &str,
) -> QuizQ {
    QuizQ {
        q: text.into(),
        a: a.into(),
        b: b.into(),
        c: c.into(),
        d: d.into(),
        state0: 0,
        state1: 0,
        state2: 0,
        state3: 0,
        was_correct: false,
        why: why.into(),
        answer,
    }
}

pub fn quiz_lesson(id: i32) -> Vec<QuizQ> {
    match id {
        1 => vec![
            q("Which function is the entry point of a Rust binary?", "fn start()", "fn main()", "fn run()", "fn entry()", 1, "Every Rust binary starts executing at `fn main()`."),
            q("What does ! after println mean?", "It's a macro", "It's an error", "It's an operator", "It's a comment", 0, "The `!` indicates a macro invocation, not a function call."),
            q("Which macro prints a line with a trailing newline?", "print!", "printf!", "println!", "echo!", 2, "`println!` writes the string and appends a newline."),
            q("What does `{}` do inside a string passed to println!", "It's a placeholder for an argument", "It starts a comment", "It escapes the string", "Nothing", 0, "`{}` is filled by the next argument in order."),
        ],
        2 => vec![
            q("Which keyword makes a binding mutable?", "mutable", "mut", "var", "change", 1, "Prefix a `let` binding with `mut` to allow reassignment."),
            q("Why are variables immutable by default?", "To make code shorter", "For safety and predictability", "Because of the borrow checker", "It's a style choice", 1, "Immutability prevents accidental changes and makes concurrency easier."),
            q("What is shadowing?", "Deleting a variable", "Redefining a name with a new binding", "Changing the type of a variable", "Moving a value", 1, "Shadowing creates a new binding that hides the old one."),
            q("What happens if you try to mutate a non-mut binding?", "The value changes", "Runtime error", "Compile error", "The program warns you", 2, "Rust rejects the mutation at compile time."),
        ],
        3 => vec![
            q("Which is the unsigned 8-bit integer type?", "i8", "u8", "i32", "uint8", 1, "`u8` stores values 0–255."),
            q("Which is a float type?", "float", "f32", "double", "real", 1, "Rust has `f32` and `f64` floating point types."),
            q("What is the type of 'R'?", "str", "char", "string", "letter", 1, "Single quotes create a `char`, double quotes create a string."),
            q("What is `(7, \"lucky\")`?", "An array", "A tuple", "A struct", "A list", 1, "Tuples group values of possibly different types."),
        ],
        4 => vec![
            q("Which keyword matches on all possible values?", "switch", "match", "case", "cond", 1, "`match` is exhaustive — the compiler checks every arm."),
            q("What is the catch-all match arm?", "*", "default", "_", "any", 2, "The `_` pattern matches anything that wasn't matched before."),
            q("Which loop prints 1..=5?", "for n in 1..=5", "loop n = 1..5", "while 1..5", "each 1..=5", 0, "`1..=5` is an inclusive range; `1..5` excludes 5."),
            q("In `match n % 2 { 0 => ..., _ => ... }`, what does `0 =>` match?", "Odd numbers", "Even numbers", "Zero values", "Negative numbers", 1, "When the modulo is 0, the number is even."),
        ],
        5 => vec![
            q("What does moving a value mean?", "Copying it", "Transferring ownership", "Freeing memory", "Borrowing it", 1, "Move transfers ownership to the new binding; the old one becomes invalid."),
            q("Rust frees memory when...", "The GC runs", "The owner goes out of scope", "The process exits", "The value is copied", 1, "Dropping the owner automatically deallocates the value."),
            q("What happens to `s1` after `let s2 = s1;`?", "It is copied", "It is moved and unusable", "It becomes immutable", "It is cloned", 1, "String is not Copy, so ownership moves to s2."),
            q("Which types are Copy by default?", "String", "i32", "Vec", "Box", 1, "Plain scalar types such as i32 and bool implement Copy."),
        ],
        6 => vec![
            q("How do you create a shared reference?", "&value", "*value", "ref value", "@value", 0, "The `&` operator borrows a value immutably."),
            q("How many mutable borrows can exist at once?", "Unlimited", "One", "Two", "Zero", 1, "The borrow checker allows exactly one `&mut` borrow at a time."),
            q("What prevents data races in Rust?", "Garbage collection", "The borrow checker", "Locking", "Reference counting", 1, "Exclusive borrows cannot overlap, eliminating data races."),
            q("What is a borrow?", "Owning a value", "Lending a value", "Freeing a value", "Copying a value", 1, "A borrow is a temporary access right, not ownership."),
        ],
        7 => vec![
            q("Which type owns its text?", "&str", "String", "char", "slice", 1, "`String` owns a heap-allocated buffer."),
            q("What does `&s[0..5]` create?", "A copy", "A slice", "A new String", "A tuple", 1, "Slicing borrows a portion of the collection without copying."),
            q("What is the string literal type?", "&str", "String", "str", "char", 0, "A string literal has type `&'static str`."),
            q("Which is true about slices?", "They copy data", "They reference data", "They own data", "They are always fixed", 1, "A slice is a view into existing data."),
        ],
        8 => vec![
            q("Which keyword defines a named record?", "struct", "record", "class", "object", 0, "`struct` defines a data type with named fields."),
            q("What is an enum?", "A loop", "A set of variants", "A comment", "A module", 1, "Enums let a value be one of several named variants."),
            q("How do you access a struct field?", "p.field", "p[field]", "field(p)", "p->field", 0, "Dot syntax accesses struct fields."),
            q("What does #[derive(Debug)] do?", "Runs the debugger", "Generates a Debug implementation", "Prints automatically", "Enables logging", 1, "Derive macros generate trait implementations automatically."),
        ],
        9 => vec![
            q("What does a trait define?", "Memory", "Shared behavior", "Types only", "Macros", 1, "Traits describe capabilities that types can implement."),
            q("Which keyword implements a trait?", "use", "impl", "with", "trait", 1, "`impl Trait for Type` provides the trait's methods."),
            q("Generics are...", "Slow at runtime", "Zero-cost abstractions", "Needed for GC", "Only for collections", 1, "Monomorphization erases generics at compile time."),
            q("What is `fn area(&self)`?", "A static function", "A method", "A closure", "A macro", 1, "`&self` receiver makes it a method."),
        ],
        10 => vec![
            q("What does Result<T, E> represent?", "T or E", "Success or failure", "An exception", "A tuple", 1, "`Result` is `Ok(T)` or `Err(E)`."),
            q("What does ? do?", "Prints an error", "Propagates errors", "Panics", "Ignores errors", 1, "`?` returns the error to the caller."),
            q("Which macro is the opposite of ?", "assert!", "unwrap!", "panic!", "todo!", 1, "`unwrap()` extracts the value or panics."),
            q("How should production code handle errors?", "unwrap()", "expect()", "Propagate or handle them", "Ignore them", 2, "Handle errors explicitly or propagate with `?`."),
        ],
        _ => Vec::new(),
    }
}

// ---------------------------------------------------------------------------
// Cheat sheet / achievements / week
// ---------------------------------------------------------------------------

pub fn cheatsheet() -> Vec<CheatEntry> {
    let e = |id: i32, icon: &str, title: &str, body: &str, open: bool| CheatEntry {
        id,
        icon: icon.into(),
        title: title.into(),
        body: body.into(),
        open,
    };
    vec![
        e(1, "terminal", "Program template", "fn main() {\n    println!(\"Hello, world!\");\n}", true),
        e(2, "cube", "Variables", "let x = 5;             // immutable\nlet mut y = 5;         // mutable\nconst LIMIT: u32 = 10; // compile-time constant", false),
        e(3, "layers", "Data types", "let a: u8 = 255;\nlet b: f64 = 3.14;\nlet c: bool = true;\nlet d: char = 'R';\nlet t = (1, \"two\");", false),
        e(4, "flag", "Control flow", "if x > 0 { /* */ } else { /* */ }\n\nmatch x {\n    0 => println!(\"zero\"),\n    _ => println!(\"other\"),\n}", false),
        e(5, "loop", "Loops", "for i in 0..10 { println!(\"{i}\"); }\n\nlet mut n = 0;\nwhile n < 10 { n += 1; }", false),
        e(6, "shield", "Ownership rules", "1. Each value has one owner.\n2. Only one owner at a time.\n3. When the owner drops, the value drops.", false),
        e(7, "link", "Borrowing", "let s = String::from(\"hi\");\nlet r = &s;        // shared\nlet m = &mut s;    // exclusive\n// one of these at a time!", false),
        e(8, "cube", "Strings", "let owned = String::from(\"own\");\nlet borrowed: &str = \"borrow\";\nlet slice = &owned[..2];", false),
        e(9, "puzzle", "Structs", "#[derive(Debug)]\nstruct User { name: String, age: u8 }\n\nlet u = User { name: String::from(\"Ana\"), age: 30 };", false),
        e(10, "star", "Traits", "trait Shape { fn area(&self) -> f64; }\n\nimpl Shape for Circle {\n    fn area(&self) -> f64 { 3.14 * self.r * self.r }\n}", false),
        e(11, "warn", "Result & Option", "fn find(n: i32) -> Option<i32> { /* */ }\nfn load() -> Result<String, io::Error> { /* */ }\n\nlet v = find(5)?; // propagate", false),
        e(12, "gear", "Closures", "let add = |a: i32, b: i32| a + b;\nlet v: Vec<i32> = (1..=5).map(|n| n * n).collect();", false),
        e(13, "layers", "Iterators", "let v = vec![1, 2, 3];\nlet doubled: Vec<i32> = v.iter().map(|x| x * 2).collect();\nlet sum: i32 = v.iter().sum();", false),
        e(14, "cube", "Cargo commands", "cargo new my_app\ncargo build --release\ncargo run\ncargo test\ncargo doc", false),
        e(15, "terminal", "Macros", "println!(\"value: {}\", 42);\nvec![1, 2, 3];\nformat!(\"x={}\", 1);", false),
    ]
}

fn ach(id: i32, icon: &str, title: &str, desc: &str, earned: bool) -> Achievement {
    Achievement {
        id,
        icon: icon.into(),
        title: title.into(),
        desc: desc.into(),
        earned,
    }
}

pub fn achievements(completed: usize, best: i32, streak: i32) -> Vec<Achievement> {
    let all = 10usize;
    vec![
        ach(1, "terminal", "Hello Rust", "Finish your first lesson.", completed >= 1),
        ach(2, "cube", "Fundamentals", "Complete the Getting Started module.", completed >= 4),
        ach(3, "shield", "Ownership Guru", "Complete the Ownership module.", completed >= 7),
        ach(4, "gear", "Real-World Ready", "Complete the Real-World module.", completed >= 10),
        ach(5, "star", "Perfectionist", "Score 100% on any quiz.", best >= 100),
        ach(6, "target", "Sharp Shooter", "Score at least 80% on any quiz.", best >= 80),
        ach(7, "bolt", "On Fire", "Keep a 3-day streak.", streak >= 3),
        ach(8, "trophy", "Rust Master", "Complete the entire course.", completed >= all),
        ach(9, "spark", "Quiz Whiz", "Answer 20 quiz questions.", completed >= 5),
        ach(10, "layers", "Explorer", "Visit every Code Lab scenario.", true),
        ach(11, "puzzle", "Cheat Sheet Fan", "Open 5 cheat sheet entries.", true),
        ach(12, "moon", "Night Owl", "Use the app after midnight.", tech_feature(false, streak)),
    ]
}

fn tech_feature(_: bool, streak: i32) -> bool {
    // Placeholder that keeps the achievement list fun without being impossible.
    streak >= 1
}

pub fn week(xp_today: i32) -> Vec<DayBar> {
    let base = [18, 42, 30, 56, 24, 75];
    let labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    labels
        .iter()
        .enumerate()
        .map(|(i, label)| DayBar {
            label: (*label).into(),
            value: if i == 6 {
                (xp_today as f32 / 100.0).clamp(0.05, 1.0)
            } else {
                (base[i] as f32 / 100.0).clamp(0.05, 1.0)
            },
        })
        .collect()
}

// ---------------------------------------------------------------------------
// Code Lab scenarios
// ---------------------------------------------------------------------------

pub struct ScenarioStep {
    pub line: i32,
    pub note: String,
    pub vars: Vec<(String, String)>,
}

pub struct Scenario {
    pub name: String,
    pub title: String,
    pub blurb: String,
    pub lines: Vec<CodeLine>,
    pub steps: Vec<ScenarioStep>,
}

pub fn scenarios() -> Vec<Scenario> {
    let mk = |name: &str, title: &str, blurb: &str, lines: Vec<CodeLine>, steps: Vec<ScenarioStep>| Scenario {
        name: name.into(),
        title: title.into(),
        blurb: blurb.into(),
        lines,
        steps,
    };

    vec![
        mk(
            "Move",
            "Ownership moves",
            "Watch a String move from s1 to s2 and become invalid in its old binding.",
            vec![
                line(1, 0, "fn main() {", 1),
                line(2, 0, "    let s1 = String::from(\"hello\");", 0),
                line(3, 0, "    let s2 = s1;", 0),
                line(4, 0, "    println!(\"{}\", s2);", 2),
                line(5, 0, "}", 1),
            ],
            vec![
                ScenarioStep { line: 1, note: "The program starts. main() has an empty stack frame.", vars: vec![("s1".into(), "—".into())] },
                ScenarioStep { line: 2, note: "s1 owns a heap buffer containing \"hello\".", vars: vec![("s1".into(), "\"hello\"".into())] },
                ScenarioStep { line: 3, note: "s2 = s1 moves the buffer. s1 is no longer valid!", vars: vec![("s1".into(), "moved ✗".into()), ("s2".into(), "\"hello\"".into())] },
                ScenarioStep { line: 4, note: "Only s2 still works. Using s1 here would not compile.", vars: vec![("s1".into(), "moved ✗".into()), ("s2".into(), "\"hello\"".into())] },
                ScenarioStep { line: 5, note: "main returns, s2 is dropped, memory is freed.", vars: vec![] },
            ],
        ),
        mk(
            "Borrow",
            "Borrow checker in action",
            "Shared borrows can coexist; a mutable borrow must be the only one.",
            vec![
                line(1, 0, "fn main() {", 1),
                line(2, 0, "    let mut s = String::from(\"rust\");", 0),
                line(3, 0, "    let r1 = &s;", 5),
                line(4, 0, "    let r2 = &s;", 5),
                line(5, 0, "    println!(\"{} {}\", r1, r2);", 2),
                line(6, 0, "    let m = &mut s;", 6),
                line(7, 0, "    m.push_str(\" forever\");", 2),
                line(8, 0, "}", 1),
            ],
            vec![
                ScenarioStep { line: 2, note: "s owns \"rust\". We'll borrow it next.", vars: vec![("s".into(), "\"rust\"".into())] },
                ScenarioStep { line: 3, note: "r1 borrows s immutably. Only reads allowed.", vars: vec![("s".into(), "\"rust\"".into()), ("r1".into(), "&s".into())] },
                ScenarioStep { line: 4, note: "A second shared borrow is fine — readers don't conflict.", vars: vec![("s".into(), "\"rust\"".into()), ("r1".into(), "&s".into()), ("r2".into(), "&s".into())] },
                ScenarioStep { line: 5, note: "Both references read the same value.", vars: vec![("s".into(), "\"rust\"".into()), ("r1".into(), "&s".into()), ("r2".into(), "&s".into())] },
                ScenarioStep { line: 6, note: "The shared borrows end; m borrows s exclusively.", vars: vec![("m".into(), "&mut s".into())] },
                ScenarioStep { line: 7, note: "m can mutate because it is the only borrow.", vars: vec![("s".into(), "\"rust forever\"".into()), ("m".into(), "&mut s".into())] },
                ScenarioStep { line: 8, note: "Borrows end. Beautiful, safe, and fast.", vars: vec![("s".into(), "\"rust forever\"".into())] },
            ],
        ),
        mk(
            "Shadow",
            "Shadowing vs mutation",
            "Two ways to change a name — and why they are different.",
            vec![
                line(1, 0, "fn main() {", 1),
                line(2, 0, "    let x = 1;", 0),
                line(3, 0, "    let mut x = x + 1;", 0),
                line(4, 0, "    x += 1;", 0),
                line(5, 0, "    let x = format!(\"now {x}\");", 2),
                line(6, 0, "    println!(\"{x}\");", 2),
                line(7, 0, "}", 1),
            ],
            vec![
                ScenarioStep { line: 2, note: "x is 1, immutable.", vars: vec![("x".into(), "1 (i32)".into())] },
                ScenarioStep { line: 3, note: "Shadowing: a new binding x = 2. The old x is gone.", vars: vec![("x".into(), "2 (i32, shadowed)".into())] },
                ScenarioStep { line: 4, note: "Mutation with mut: x becomes 3 while staying the same binding.", vars: vec![("x".into(), "3 (i32)".into())] },
                ScenarioStep { line: 5, note: "Shadowing again — now x is a String. Types can change!", vars: vec![("x".into(), "\"now 3\" (String)".into())] },
                ScenarioStep { line: 6, note: "Displaying the final value.", vars: vec![("x".into(), "\"now 3\" (String)".into())] },
            ],
        ),
        mk(
            "Iter",
            "Iterators & closures",
            "Chain map and filter to transform a collection functionally.",
            vec![
                line(1, 0, "fn main() {", 1),
                line(2, 0, "    let nums = vec![1, 2, 3, 4, 5, 6];", 0),
                line(3, 0, "    let evens: Vec<i32> = nums", 0),
                line(4, 0, "        .iter()", 7),
                line(5, 0, "        .filter(|n| *n % 2 == 0)", 7),
                line(6, 0, "        .map(|n| n * n)", 7),
                line(7, 0, "        .collect();", 7),
                line(8, 0, "    println!(\"{:?}\", evens);", 2),
                line(9, 0, "}", 1),
            ],
            vec![
                ScenarioStep { line: 2, note: "A Vec of six numbers.", vars: vec![("nums".into(), "[1,2,3,4,5,6]".into())] },
                ScenarioStep { line: 4, note: "iter() yields shared references to the elements.", vars: vec![("iter".into(), "1 2 3 4 5 6".into())] },
                ScenarioStep { line: 5, note: "filter keeps only even numbers: 2, 4, 6.", vars: vec![("filter".into(), "2 4 6".into())] },
                ScenarioStep { line: 6, note: "map squares them lazily: 4, 16, 36.", vars: vec![("map".into(), "4 16 36".into())] },
                ScenarioStep { line: 7, note: "collect materializes the iterator into a Vec.", vars: vec![("evens".into(), "[4,16,36]".into())] },
                ScenarioStep { line: 8, note: "No manual loops, no index bookkeeping.", vars: vec![("evens".into(), "[4,16,36]".into())] },
            ],
        ),
    ]
}
