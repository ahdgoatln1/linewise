import ast
import html
import re

import streamlit as st

st.set_page_config(page_title="Linewise", page_icon="✎", layout="centered")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap');
.stApp{background:#f3ede2}
[data-testid="stHeader"]{background:transparent}
.block-container{max-width:760px;padding-top:2rem}
.stMarkdown,.stMarkdown p,.stMarkdown li,.stMarkdown h3,.stMarkdown h4,label,label p,[data-testid="stRadio"] p,[data-testid="stExpander"] summary p{color:#26221d!important}
h1,h2,h3,.hero h1{font-family:'Fraunces',Georgia,serif!important;color:#26221d!important}
.hero{border-bottom:2px solid #26221d;margin-bottom:6px;padding-bottom:10px}
.hero h1{font-size:2.6rem;margin:0;letter-spacing:-.5px}
.hero p{margin:2px 0 0;color:#5f574b!important;font-size:1.05rem}
.stTabs [data-baseweb="tab-list"]{gap:22px;border-bottom:1px solid #d9cfbc}
.stTabs [data-baseweb="tab"] p{font-size:1.05rem;font-weight:600;color:#6d6455!important}
.stTabs [aria-selected="true"] p{color:#b4492f!important}
.stTabs [data-baseweb="tab-highlight"]{background:#b4492f}
.step{margin:22px 0 4px;font-weight:600;color:#26221d}
.step .n{display:inline-block;width:26px;height:26px;line-height:26px;text-align:center;background:#b4492f;color:#f3ede2;border-radius:50%;margin-right:9px;font-size:.85rem}
.why{color:#5f574b!important;font-size:.95rem;margin:4px 0 0}
.card{border:1px solid #d9cfbc;border-left:4px solid #8a8070;background:#faf5ea;padding:10px 14px;margin:12px 0;border-radius:2px;color:#26221d}
.card.ok{border-left-color:#4a5d3a}.card.bad{border-left-color:#b4492f}
.card b{color:#26221d}.card p{margin:4px 0;color:#26221d}
.stButton button,.stFormSubmitButton button{background:#26221d;color:#f3ede2;border:0;border-radius:3px;padding:.45rem 1rem}
.stButton button:hover,.stFormSubmitButton button:hover{background:#b4492f;color:#fff}
.stTextInput input{background:#fffaf0;color:#26221d;border:1px solid #cdbfa6;font-family:ui-monospace,Menlo,Consolas,monospace}
[data-testid="stExpander"]{border:1px solid #d9cfbc;background:#faf5ea;border-radius:2px}
</style>
<div class="hero"><h1>Linewise</h1><p>Learn Python one line at a time. Read a step, type it, watch it work.</p></div>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------- safe runner
class Blocked(Exception):
    pass


NODES = (
    ast.Module, ast.Expr, ast.Assign, ast.AugAssign, ast.If, ast.For, ast.While,
    ast.Break, ast.Continue, ast.Pass, ast.FunctionDef, ast.Return, ast.Call,
    ast.Name, ast.Constant, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
    ast.List, ast.Tuple, ast.Dict, ast.Subscript, ast.Slice, ast.JoinedStr,
    ast.FormattedValue, ast.IfExp, ast.Attribute, ast.arguments, ast.arg,
    ast.keyword, ast.expr_context, ast.operator, ast.unaryop, ast.boolop, ast.cmpop,
)
METHODS = {"append", "upper", "lower", "join", "split", "strip", "replace", "title",
           "count", "sort", "reverse", "pop", "capitalize", "items", "keys", "values",
           "startswith", "endswith", "index", "extend", "insert"}


def check_tree(tree):
    for n in ast.walk(tree):
        if not isinstance(n, NODES):
            raise Blocked(type(n).__name__ + " is not available in practice mode")
        if isinstance(n, ast.Name) and n.id.startswith("_"):
            raise Blocked("names that start with _ are not allowed")
        if isinstance(n, ast.Attribute) and n.attr not in METHODS:
            raise Blocked("." + n.attr + " is not available in practice mode")
        if isinstance(n, ast.AugAssign) and isinstance(n.op, (ast.Mult, ast.Pow)):
            raise Blocked("*= and **= are not available; write x = x * 2 instead")
        if isinstance(n, ast.FormattedValue) and n.format_spec is not None:
            raise Blocked("format specs like {x:>5} are not available")


def _op(op, a, b):
    if op == "*":
        for x, y in ((a, b), (b, a)):
            if isinstance(x, (str, list)) and isinstance(y, int) and len(x) * y > 5000:
                raise MemoryError("that would build something far too big")
        return a * b
    if op == "**":
        if isinstance(b, int) and b > 300:
            raise MemoryError("that power is too big")
        return a ** b
    if isinstance(a, str):
        raise TypeError("text formatting with % is not available here")
    return a % b


class Guard(ast.NodeTransformer):
    def visit_BinOp(self, n):
        self.generic_visit(n)
        sym = {ast.Mult: "*", ast.Pow: "**", ast.Mod: "%"}.get(type(n.op))
        if not sym:
            return n
        call = ast.Call(ast.Name("__op", ast.Load()), [ast.Constant(sym), n.left, n.right], [])
        return ast.copy_location(call, n)

    def _loop(self, n):
        self.generic_visit(n)
        n.body.insert(0, ast.Expr(ast.Call(ast.Name("__tick", ast.Load()), [], [])))
        return n

    visit_For = visit_While = _loop


def run(code):
    out, ticks = [], [0]

    def pr(*a, sep=" ", end="\n"):
        out.append(sep.join(str(x) for x in a) + end)
        if sum(len(x) for x in out) > 20000:
            raise MemoryError("too much output")

    def tick():
        ticks[0] += 1
        if ticks[0] > 5000:
            raise RuntimeError("a loop ran more than 5000 times, so it was stopped")

    safe = {"len": len, "range": range, "str": str, "int": int, "float": float,
            "round": round, "abs": abs, "min": min, "max": max, "bool": bool, "print": pr}
    env = {"__builtins__": safe, "__tick": tick, "__op": _op}
    try:
        tree = ast.parse(code)
        check_tree(tree)
        tree = ast.fix_missing_locations(Guard().visit(tree))
        exec(compile(tree, "<practice>", "exec"), env)
        return "".join(out), None
    except Exception as e:  # noqa: BLE001
        return "".join(out), e


# ---------------------------------------------------------------- explanations
def depth(code):
    c = re.sub(r"(\"|')(?:\\.|(?!\1).)*\1", "", code)
    c = re.sub(r"#.*", "", c)
    return sum(c.count(x) for x in "([{") - sum(c.count(x) for x in ")]}")


def why_syntax(e, t):
    m = (e.msg or "").lower()
    if "expected ':'" in m:
        return ("SyntaxError: a colon is missing", "Lines that start a block (if, elif, else, for, while, def) must end with a colon.", t.rstrip() + ":")
    if "unterminated string" in m:
        return ("SyntaxError: a quote is never closed", "Text needs a quote at the start and the same quote at the end.", 'print("hello")')
    if "unmatched" in m:
        return ("SyntaxError: extra closing bracket", "You closed a bracket that was never opened.", "Delete the extra ) ] or } .")
    if "missing parentheses" in m:
        return ("SyntaxError: print needs brackets", "In Python 3, print is used like print(...).", "print(" + t[5:].strip() + ")")
    if "maybe you meant '=='" in m:
        return ("SyntaxError: = versus ==", "One = stores a value. Two == compares two values.", t.replace("=", "==", 1))
    if "indent" in m:
        return ("IndentationError: " + e.msg, "A line right after a colon must be indented inside it, and lines outside must line up with the block.", "Let the app indent for you. Press Enter on an empty line to step out of a block.")
    if "cannot assign" in m:
        return ("SyntaxError: cannot store a value there", "The left side of = must be a plain name, like score.", "score = 10")
    return ("SyntaxError: " + (e.msg or "invalid syntax"), "Python could not read this line.", "Check quotes, brackets, colons and spelling.")


def why_run(e):
    m, t = str(e), type(e).__name__
    if isinstance(e, Blocked):
        return ("Not available here: " + m, "Practice mode only allows beginner features so it stays safe.", "Stick to print, variables, if, for, while, def and lists.")
    if t == "NameError":
        g = re.search(r"'(\w+)'", m)
        n = g.group(1) if g else "it"
        if n == "input":
            return ("input() is not available here", "This practice box cannot ask questions while running.", "Store a value instead: answer = 5")
        return (f"NameError: {n} does not exist yet", f"This line uses {n}, but nothing above creates it.", f"Create it first, on an earlier line:\n{n} = 0")
    if t == "ZeroDivisionError":
        return ("ZeroDivisionError", "You divided by zero, which has no answer.", "Divide by a number that is not 0.")
    if t == "TypeError":
        return ("TypeError: " + m, "These values do not mix, for example text plus a number.", 'Use an f-string:\nprint(f"Age: {age}")')
    if t == "IndexError":
        return ("IndexError: " + m, "You asked for a position that is not in the list. Counting starts at 0.", "A list of 3 items has positions 0, 1, 2.")
    return (f"{t}: {m}", "Running the program fails once this line is added.", "Fix the cause above, or press Undo and try another approach.")


def note(t):
    if re.match(r"#", t):
        return "A comment. Python skips it; it is for people reading the code."
    if re.match(r"print\(", t):
        return "Shows something in the output box. This is how you check what your code does."
    if re.match(r"(if|elif)\b", t):
        return "A decision. The indented lines under it only run when it is true."
    if re.match(r"else\b", t):
        return "The fallback: runs when the if above was false."
    if re.match(r"(for|while)\b", t):
        return "A loop. The indented lines under it repeat. Something must change so it can stop."
    if re.match(r"def\b", t):
        return "Creates a function: a named chunk of code. Nothing happens until you call its name."
    if re.match(r"return\b", t):
        return "Sends a value back out of the function and leaves it."
    if re.match(r"\w+\s*=[^=]", t):
        return "Stores a value under a name so you can use it later."
    return "Accepted. The output box shows what the whole program does so far."


# ---------------------------------------------------------------- tutorial content
LESSONS = [
    {"t": "Make the computer talk", "intro": "Your first program. You will type two lines. Each one tells Python to show a message.",
     "steps": [
         ("Type this line exactly. Keep the brackets and both quote marks.", 'print("Hello, world")', "print means show. The brackets hold what to show. Quotes tell Python it is text."),
         ("Add a second line underneath it.", 'print("I am learning Python")', "Python runs lines from top to bottom, one after another."),
     ]},
    {"t": "Remember things", "intro": "A variable is a labelled box. You put something in, give it a name, and use it later.",
     "steps": [
         ("Make a box called name. Put your own name between the quotes.", 'name = "Sam"', "The = sign stores what is on the right into the name on the left."),
         ("Make a box called age. Numbers have no quotes.", "age = 20", "Python treats 20 as a number, so you can do maths with it."),
         ("Show the name.", 'print("My name is", name)', "Commas let print show several things on one line."),
         ("Mix words and boxes in one sentence. Note the f before the first quote.", 'print(f"{name} is {age} years old")', "An f-string swaps each {box} for what is inside it."),
         ("Change a box, then show it again.", 'age = age + 1\nprint("Next year:", age)', "Python reads the right side first (20 + 1), then stores 21 back into age."),
     ]},
    {"t": "Make decisions", "intro": "Programs choose what to do. After a line ending in a colon, the next lines are indented: press the space bar 4 times, or Tab.",
     "steps": [
         ("Make a box for the temperature.", "temperature = 24", "Change the number later to see different results."),
         ("Type the if block. The second line starts with 4 spaces.", 'if temperature > 30:\n    print("It is hot")', "If the condition is true, the indented line runs. If not, Python skips it."),
         ("Add a second question underneath. elif means else if.", 'elif temperature > 18:\n    print("Nice and warm")', "Python only checks it when the first question was false."),
         ("Finish with a fallback.", 'else:\n    print("Bring a jacket")', "else catches everything the questions above did not."),
     ]},
    {"t": "Repeat yourself", "intro": "A loop repeats lines so you do not have to type them again and again.",
     "steps": [
         ("Count with a for loop.", 'for i in range(5):\n    print("Round", i)', "range(5) gives 0, 1, 2, 3, 4. Python counts from 0."),
         ("Add up the numbers 1 to 5.", 'total = 0\nfor n in range(1, 6):\n    total = total + n\nprint("Total:", total)', "The last line is not indented, so it runs once, after the loop. Result: 15."),
         ("Count down with a while loop.", 'count = 3\nwhile count > 0:\n    print(count)\n    count = count - 1\nprint("Liftoff")', "while repeats as long as the condition is true. count - 1 makes it end."),
     ]},
    {"t": "Draw a heart", "intro": "Build a picture out of text. Each line of the list is one row of the heart. Type the brackets carefully.",
     "steps": [
         ("Create the heart. Type every row, including the commas.", '''heart = [
    "  ***   ***  ",
    " ***** ***** ",
    "*************",
    "*************",
    " *********** ",
    "  *********  ",
    "   *******   ",
    "    *****    ",
    "     ***     ",
    "      *      ",
]''', "A list holds many items in order. Each row has 13 characters so the shape lines up."),
         ("Print every row.", "for line in heart:\n    print(line)", "The loop takes one row at a time and prints it, top to bottom."),
         ("Swap the stars for real hearts and draw it again.", 'char = "♥"\nfor line in heart:\n    print(line.replace("*", char))', "replace swaps every * for the symbol in char. Change char to any symbol you like."),
         ("Finish with a row of hearts.", 'print("♥ " * 7)', "Multiplying text repeats it. Here, 7 times."),
     ]},
]

EXPLAIN = [
    ("What is code?", "Code is a list of instructions for the computer, written in a language it understands. Python runs your instructions from the top line to the bottom line, one at a time. If a line is wrong, Python stops and tells you where."),
    ("Symbols you will keep seeing", "- `=` stores a value: `age = 20`\n- `==` asks if two things are equal: `age == 20`\n- `:` at the end of a line opens a block (if, for, while, def)\n- Indentation (4 spaces) shows which lines belong inside a block\n- Quotes `\"like this\"` mark text\n- Brackets `( )` hold what you give to something, like `print(...)`\n- `[ ]` make a list\n- `#` starts a comment that Python ignores"),
    ("How to read an error", "An error is not a failure. It is Python pointing at the problem. Read the first words (like NameError or SyntaxError) and the short sentence after them. NameError means you used a name that does not exist yet. SyntaxError means Python cannot read the line, usually a missing quote, bracket or colon."),
    ("Small word list", "- **Variable**: a labelled box that holds a value\n- **String**: text, written in quotes\n- **Integer**: a whole number\n- **List**: several values in order, in `[ ]`\n- **Loop**: lines that repeat\n- **Function**: a named chunk of code you can reuse\n- **Condition**: a question with a true or false answer"),
    ("How the Practice tab checks your line", "When you press Enter, the app adds your line to the program above it and tests three things: the shape (colons, brackets, indentation), whether Python can read it, and whether the whole program still runs, for example no names that were never created. If all pass, the line is kept. If not, the line is thrown away and you get the reason and a fix."),
    ("Practice-mode limits", "To stay safe, Practice runs a beginner subset: print, variables, numbers, text, lists, if, for, while, def, return. No input(), imports or files. Loops stop after 5000 rounds."),
]


# ---------------------------------------------------------------- practice logic
def prog(ls):
    c = "\n".join(ls)
    if ls and ls[-1].rstrip().endswith(":"):
        c += "\n" + " " * (len(ls[-1]) - len(ls[-1].lstrip()) + 4) + "pass"
    return c


def rej(line, what, why, fix):
    st.session_state.msg = {"k": "bad", "line": line, "what": what, "why": why, "fix": fix}


def submit():
    s = st.session_state
    t = (s.get("raw") or "").strip()
    if not t:
        if s.lines and s.lines[-1].rstrip().endswith(":"):
            s.msg = {"k": "n", "title": "Not yet", "text": "The block above needs at least one indented line inside it first."}
        elif s.lvl:
            s.lvl -= 1
            s.msg = {"k": "n", "title": "Stepped out", "text": "Back one level. Your next line goes outside the block."}
        else:
            s.msg = {"k": "n", "title": "Empty", "text": "Type a line first, then press Enter."}
        return
    open_before = depth("\n".join(s.lines)) > 0
    line = " " * (4 * s.lvl + (4 if open_before else 0)) + t
    cand = s.lines + [line]
    if depth("\n".join(cand)) > 0:
        s.lines = cand
        s.msg = {"k": "ok", "title": "Accepted", "text": "A bracket is still open. Keep typing the rest, and close it with ) ] or }. The program is checked once it is closed."}
        return
    if re.match(r"(elif|else)\b", t):
        ind = 4 * s.lvl
        prev = [x for x in s.lines if x.strip() and len(x) - len(x.lstrip()) <= ind]
        if not prev or len(prev[-1]) - len(prev[-1].lstrip()) != ind or not re.match(r"(if|elif|for|while)\b", prev[-1].strip()):
            return rej(line, "else/elif has no matching if", "else and elif must continue an if block, lined up with it.", "Write the if first, then step out of its block (empty Enter) before typing else.")
    code = prog(cand)
    try:
        ast.parse(code)
    except SyntaxError as e:
        return rej(line, *why_syntax(e, t))
    o, err = run(code)
    if err:
        return rej(line, *why_run(err))
    s.lines, s.out = cand, o
    s.lvl = s.lvl + 1 if t.endswith(":") else s.lvl
    s.msg = {"k": "ok", "title": "Accepted", "text": note(t)}


def undo():
    s = st.session_state
    if not s.lines:
        return
    s.lines.pop()
    s.out = run(prog(s.lines))[0] if s.lines else ""
    last = next((x for x in reversed(s.lines) if x.strip()), "")
    s.lvl = (len(last) - len(last.lstrip())) // 4 + (1 if last.rstrip().endswith(":") else 0)
    s.msg = {"k": "n", "title": "Undone", "text": "Last line removed."}


def reset():
    s = st.session_state
    s.lines, s.lvl, s.out, s.msg = [], 0, "", None


def card(kind, title, text):
    st.markdown(f'<div class="card {kind}"><b>{html.escape(title)}</b><p>{html.escape(text)}</p></div>', unsafe_allow_html=True)


def show_error(e):
    what, why, fix = why_run(e)
    card("bad", what, why)
    st.code(fix, language="python")


# ---------------------------------------------------------------- tabs
for k, v in {"lines": [], "lvl": 0, "out": "", "msg": None}.items():
    st.session_state.setdefault(k, v)

tab_learn, tab_practice, tab_explain = st.tabs(["Learn", "Practice", "Explain"])

with tab_learn:
    names = [f"{i + 1}. {L['t']}" for i, L in enumerate(LESSONS)]
    pick = st.radio("Lesson", names, label_visibility="collapsed")
    L = LESSONS[names.index(pick)]
    st.markdown(f"### {L['t']}")
    st.write(L["intro"])
    for i, (do, code, why) in enumerate(L["steps"], 1):
        st.markdown(f'<div class="step"><span class="n">{i}</span>{html.escape(do)}</div>', unsafe_allow_html=True)
        st.code(code, language="python")
        st.markdown(f'<p class="why">{html.escape(why)}</p>', unsafe_allow_html=True)
    st.markdown("---")
    st.write("Typed everything? Press the button to run the whole lesson and compare with your own result.")
    if st.button("Run this lesson", key="run_" + pick):
        o, e = run("\n".join(c for _, c, _ in L["steps"]))
        st.markdown("**Output**")
        st.code(o or "(nothing printed)")
        if e:
            show_error(e)
    st.caption("Next: open the Practice tab and type the lines yourself. The app will check each one.")

with tab_practice:
    st.markdown("Type one line at a time. If it is valid and fits the lines above, it is added. If not, it is thrown away and you are told why.")
    st.code("\n".join(st.session_state.lines) or "# your program shows up here, one accepted line at a time", language="python", line_numbers=True)
    m = st.session_state.msg
    if m:
        if m["k"] == "bad":
            card("bad", "Rejected: " + m["line"].strip(), m["what"])
            st.markdown(f"**Why:** {m['why']}")
            st.markdown("**Fix:**")
            st.code(m["fix"], language="python")
        else:
            card(m["k"], m["title"], m["text"])
    elif not st.session_state.lines:
        card("n", "Start here", 'Type  print("hi")  and press Enter.')
    lvl = st.session_state.lvl
    where = f" (inside {lvl} block{'s' if lvl > 1 else ''}, indented for you)" if lvl else ""
    with st.form("line_form", clear_on_submit=True):
        st.text_input(f"Line {len(st.session_state.lines) + 1}{where}", key="raw", placeholder="type a line and press Enter")
        st.form_submit_button("Check line", on_click=submit)
    st.caption("Empty Enter steps out of a block.")
    st.markdown("**Output**")
    st.code(st.session_state.out or "(nothing printed yet)")
    c1, c2 = st.columns(2)
    c1.button("Undo last line", on_click=undo, use_container_width=True)
    c2.button("Start over", on_click=reset, use_container_width=True)

with tab_explain:
    for title, body in EXPLAIN:
        with st.expander(title):
            st.markdown(body)
