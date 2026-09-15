"""Additive manuscript conversion; no scientific execution. Adapted from preserved converter."""

import hashlib
import json
import os
import re
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.token import Token

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "docs/dissertation/examiner_revision_2026-09-11"
OUT = SRC
source = (SRC / "TrafficTwin_Dissertation.md").read_text()
parser = MarkdownIt("commonmark").enable("table")
# Change only relative link destinations to account for the new sibling folder.
links = {}
for tok in parser.parse(source):
    for c in tok.children or []:
        if c.type not in ("link_open", "image"):
            continue
        href = c.attrGet("href") or c.attrGet("src")
        if href.startswith(("#", "https://", "http://", "assets/")):
            continue
        path, sep, anchor = href.partition("#")
        links[href] = os.path.relpath((SRC / path).resolve(), OUT) + (sep + anchor if sep else "")
md = source
for old, new in sorted(links.items(), key=lambda x: -len(x[0])):
    md = md.replace("](" + old + ")", "](" + new + ")")
(OUT / "TrafficTwin_Dissertation.md").write_text(md)
for tok in parser.parse(md):
    for c in tok.children or []:
        if c.type == "image":
            name = c.attrGet("src")
            assert (OUT / name).is_file()

# Explicit typesetting map: original formula spelling -> equivalent LaTeX.
mathmap = {
    "s = ξ × C_t / [2.2 × 1.5 × min(12, p_t) × 0.9 × min(5, g_t)]": (
        "s = \\frac{\\xi \\times C_t}{2.2 \\times 1.5 \\times \\min(12,p_t) "
        "\\times 0.9 \\times \\min(5,g_t)}"
    ),
    "p_t = (4, 4, 2)": r"p_t=(4,4,2)",
    "g_t = (40, 5, 1)": r"g_t=(40,5,1)",
    "min(Poisson(1.5), 5)": r"\min(\operatorname{Poisson}(1.5),5)",
    "0.1 + 1,000 × 8b/c": r"0.1 + 1{,}000 \times 8b/c",
    "q ≥ 0.15": r"q\geq 0.15",
    "c > 0.000000001": r"c>0.000000001",
    "T(b,q,c)": r"T(b,q,c)",
    "L[i] = 10D[i]": r"L[i]=10D[i]",
    "L_raw[i] ≥ 10⁸": r"L_{\mathrm{raw}}[i]\geq 10^{8}",
    "L[i] = L_raw[i]": r"L[i]=L_{\mathrm{raw}}[i]",
    "L[i] ≤ D[i]": r"L[i]\leq D[i]",
    "S[r] = min(W_post[r], 1,000)": r"S[r]=\min(W_{\mathrm{post}}[r],1{,}000)",
    "W_next[r] = W_post[r] − S[r]": r"W_{\mathrm{next}}[r]=W_{\mathrm{post}}[r]-S[r]",
    "floor(Q_post[r] × S[r]/W_post[r])": (
        "\\left\\lfloor Q_{\\mathrm{post}}[r]\\times S[r]/W_{\\mathrm{post}}[r]\\right\\rfloor"
    ),
    "Q[r[i]] < C": r"Q[r[i]]<C",
    "O[i,M]": r"O[i,M]",
    "H[i,M]": r"H[i,M]",
    "s[j,r[i]]": r"s[j,r[i]]",
    "j < i": r"j<i",
    "mean ± t × sample standard deviation / square root of n": (
        r"\text{mean}\pm t\times\frac{"
        r"\text{sample standard deviation}}{\sqrt{n}}"
    ),
    "1 − 0.05/(2 × 3)": r"1-0.05/(2\times 3)",
    "max(B − (1,000 − d), 0)": r"\max(B-(1{,}000-d),0)",
    "min(K, R)": r"\min(K,R)",
    "R ≥ K": r"R\geq K",
    "min(n, 2d−1)": r"\min(n,2d-1)",
    "d−1": r"d-1",
    "N/R=215/9": r"N/R=215/9",
    "N=2,488/R=10": r"N=2{,}488/R=10",
    "N=215/R=9": r"N=215/R=9",
    "N=2,488": r"N=2{,}488",
    "N=215": r"N=215",
    "K=5": r"K=5",
    "N×R": r"N\times R",
    "K×N": r"K\times N",
    "O(KNR)": r"O(KNR)",
    "O(NR)": r"O(NR)",
    "O(KN)": r"O(KN)",
    "W=82.32322692871094": r"W=82.32322692871094",
    "Q=4": r"Q=4",
    "C=6,220": r"C=6{,}220",
    "W/4": r"W/4",
    "11111111→11111110→11111111→11111110→11111111": (
        r"11111111\to11111110\to11111111"
        r"\to11111110\to11111111"
    ),
    "10⁹": r"10^{9}",
    "10⁸": r"10^{8}",
    "N_met": r"N_{\mathrm{met}}",
    "N_offered": r"N_{\mathrm{offered}}",
    "N_admitted": r"N_{\mathrm{admitted}}",
    "N_failed": r"N_{\mathrm{failed}}",
    "W_initial": r"W_{\mathrm{initial}}",
    "W_final": r"W_{\mathrm{final}}",
    "C_t": r"C_t",
    "p_t": r"p_t",
    "g_t": r"g_t",
    "W[r]": r"W[r]",
    "Q[r]": r"Q[r]",
    "a[i]": r"a[i]",
    "y[i]": r"y[i]",
    "z[i,c]": r"z[i,c]",
    "O[i]": r"O[i]",
    "D[i]": r"D[i]",
    "s[i,r]": r"s[i,r]",
    "E[i]": r"E[i]",
    "M[j]": r"M[j]",
}
mathmap.update(
    {
        "i=1,…,n": r"i=1,\ldots,n",
        "r_i": r"r_i",
        "C_r": r"C_r",
        "W_r≥0": r"W_r\geq0",
        "Q_r≥0": r"Q_r\geq0",
        "E_i": r"E_i",
        "s_i≥0": r"s_i\geq0",
        "D_i": r"D_i",
        "M≤E": r"M\leq E",
        "O_i(M)=Σ_{j<i,r_j=r_i} s_j M_j": r"O_i(M)=\sum_{\substack{j<i\\r_j=r_i}}s_jM_j",
        "H_i(M)=Σ_{j<i,r_j=r_i} M_j": r"H_i(M)=\sum_{\substack{j<i\\r_j=r_i}}M_j",
        "M⁰=E": r"M^{0}=E",
        "M³=F³(E)": r"M^{3}=F^{3}(E)",
        "O(M³)": r"O(M^{3})",
        "E_i·1{W+O_i(M³)≥D_i}": r"E_i\mathbf{1}\{W+O_i(M^{3})\geq D_i\}",
        "M³_i·1{W+O_i(M³)+s_i≤D_i}": r"M_i^{3}\mathbf{1}\{W+O_i(M^{3})+s_i\leq D_i\}",
        "M³": r"M^{3}",
        "b_i=F_i(b)": r"b_i=F_i(b)",
        "F_i": r"F_i",
        "b_1": r"b_1",
        "b_2": r"b_2",
        "s_i": r"s_i",
        "n_r": r"n_r",
        "max_r n_r": r"\max_r n_r",
        "d_r": r"d_r",
        "min(n_r,2d_r−1)": r"\min(n_r,2d_r-1)",
        "U≥V": r"U\geq V",
        "F(U)≤F(V)": r"F(U)\leq F(V)",
        "E≥b": r"E\geq b",
        "b≤U≤E": r"b\leq U\leq E",
        "2d−1": r"2d-1",
        "U=b": r"U=b",
        "U_p=1": r"U_p=1",
        "b_p=0": r"b_p=0",
        "F(U)=b": r"F(U)=b",
        "D_p": r"D_p",
        "deadline≤D_p": r"\text{deadline}\leq D_p",
        "F²(U)": r"F^{2}(U)",
        "2(d−1)−1": r"2(d-1)-1",
        "d=1": r"d=1",
        "R≥K": r"R\geq K",
    }
)
eqmap = {
    1: r"""\begin{equation}\label{eq:1}
 A=\frac{N_{\mathrm{met}}}{N_{\mathrm{offered}}}
  =\frac{\sum_i y[i]}{N_{\mathrm{offered}}};
 \qquad \text{reported percentage}=100A.
\end{equation}""",
    2: r"""\begin{equation}\label{eq:2}
 a[i]+\sum_c z[i,c]=1;\qquad y[i]\leq a[i];\qquad
 N_{\mathrm{offered}}=N_{\mathrm{admitted}}+N_{\mathrm{failed}}.
\end{equation}""",
    3: r"""\begin{equation}\label{eq:3}
 W[r]+O[i]<D[i],\quad\text{together with an available task-count place.}
\end{equation}""",
    4: r"""\begin{equation}\label{eq:4}
 \begin{aligned}
 L_{\mathrm{raw}}[i]={}&T(\mathrm{input}[i],q,c)+W[r]+O[i]+s[i,r]\\
 &+T(0.001,q,c)+f\cdot\mathbf{1}(r\neq\mathrm{ingress}[i]).
 \end{aligned}
\end{equation}""",
    5: r"""\begin{equation}\label{eq:5}
 W_{\mathrm{initial}}+\sum\text{admitted service}
 =\sum\text{served service}+W_{\mathrm{final}}.
\end{equation}""",
}
eqmap["C1"] = r"""\begin{equation}\tag{C1}\label{eq:C1}
 F_i(M)=E_i\,\mathbf{1}\{W_{r_i}+O_i(M)<D_i\}\,\mathbf{1}\{Q_{r_i}+H_i(M)<C_{r_i}\}.
\end{equation}"""
plain_escape = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "%": r"\%",
    "$": r"\$",
    "&": r"\&",
    "#": r"\#",
    "_": r"\_",
    "^": r"\textasciicircum{}",
    "~": r"\textasciitilde{}",
    "–": "--",
    "—": "---",
    "’": "'",
    "“": "``",
    "”": "''",
    "§": r"\S{}",
    "±": r"\ensuremath{\pm}",
    "·": r"\ensuremath{\cdot}",
    "×": r"\ensuremath{\times}",
    "Σ": r"\ensuremath{\sum}",
    "ξ": r"\ensuremath{\xi}",
    "⁸": r"\textsuperscript{8}",
    "⁹": r"\textsuperscript{9}",
    "→": r"\ensuremath{\to}",
    "−": r"\ensuremath{-}",
    "≠": r"\ensuremath{\neq}",
    "≤": r"\ensuremath{\leq}",
    "≥": r"\ensuremath{\geq}",
}


def esc(s: str) -> str:
    return "".join(plain_escape.get(c, c) for c in s)


refvalues = {}
mathuses = []
# Longest exact formula first, then genuine cross-references, then variable tokens.
pattern = re.compile(
    "|".join(re.escape(k) for k in sorted(mathmap, key=len, reverse=True))
    + (
        "|(?:Table|Figure|Algorithm|Proposition) "
        "(?:[A-E]\\d+|\\d+)|Equation \\(\\d+\\)|Section "
        "\\d(?:\\.\\d+)?|§\\d\\.\\d+|Appendix "
        "[A-E]|\\[(?:[1-9]|[12][0-9])\\]|\\b[WQKRNDMESHUFVijnrdqscbpt]\\b"
    )
)


def textext(s: str, refs: bool = True) -> str:
    out = []
    last = 0
    for m in pattern.finditer(s):
        # Formula substring must not bisect a word.
        x = m.group()
        a, b = m.span()
        if a and s[a - 1].isalnum():
            continue
        if b < len(s) and s[b].isalnum():
            continue
        out.append(esc(s[last:a]))
        last = b
        if x in mathmap:
            out.append("$" + mathmap[x] + "$")
            mathuses.append({"source": x, "latex": mathmap[x]})
            continue
        if re.fullmatch(r"\[\d+\]", x):
            out.append(r"\cite{ref" + x[1:-1] + "}")
            continue
        match = re.fullmatch(r"(Table|Figure|Algorithm|Proposition) ([A-E]?\d+)", x)
        if match and refs:
            label = (
                {"Table": "tab", "Figure": "fig", "Algorithm": "alg", "Proposition": "prop"}[
                    match[1]
                ]
                + ":"
                + match[2]
            )
            refvalues[label] = match[2]
            out.append(match[1] + "~" + r"\ref{" + label + "}")
            continue
        if x.startswith("Equation ") and refs:
            num = re.search(r"\d+", x)[0]
            refvalues["eq:" + num] = num
            out.append(r"Equation~\eqref{eq:" + num + "}")
            continue
        if x.startswith(("Section ", "§")) and refs:
            num = re.search(r"\d+(?:\.\d+)?", x)[0]
            refvalues["sec:" + num] = num
            out.append(
                ("Section~" if x.startswith("Section") else r"\S\,") + r"\ref{sec:" + num + "}"
            )
            continue
        if x.startswith("Appendix ") and refs:
            letter = x[-1]
            refvalues["app:" + letter] = letter
            out.append(r"Appendix~\ref{app:" + letter + "}")
            continue
        is_variable = (
            refs
            and len(x) == 1
            and not (a and s[a - 1] in "'’")
            and not (b < len(s) and s[b] == ".")
        )
        out.append("$" + x + "$" if is_variable else esc(x))
    out.append(esc(s[last:]))
    return "".join(out)


def inlines(children: list[Token], refs: bool = True) -> str:
    out = []
    i = 0
    while i < len(children):
        t = children[i]
        typ = t.type
        if typ == "text":
            out.append(textext(t.content, refs))
        elif typ == "softbreak":
            out.append("\n")
        elif typ == "hardbreak":
            out.append(r"\\" + "\n")
        elif typ == "strong_open":
            out.append(r"\textbf{")
        elif typ == "em_open":
            out.append(r"\emph{")
        elif typ in ("strong_close", "em_close"):
            out.append("}")
        elif typ == "code_inline":
            out.append(r"\path{" + t.content + "}")
        elif typ == "html_inline":
            m = re.fullmatch(r'<a id="([^"]+)">\s*</a>', t.content)
            if m:
                out.append(r"\phantomsection\label{" + m[1] + "}")
            else:
                raise ValueError(("html_inline", t.content))
        elif typ == "link_open":
            href = t.attrGet("href")
            j = i + 1
            inner = []
            while children[j].type != "link_close":
                inner.append(children[j])
                j += 1
            if re.fullmatch(r"#ref-\d+", href):
                out.append(r"\cite{ref" + href.split("-")[-1] + "}")
            elif href.startswith("#"):
                out.append(r"\hyperref[" + href[1:] + "]{" + inlines(inner, False) + "}")
            else:
                out.append(r"\href{\detokenize{" + href + "}}{" + inlines(inner, False) + "}")
            i = j
        elif typ == "image":
            raise ValueError("Image must be handled as figure")
        else:
            raise ValueError(("unexpected_inline", typ, t.content))
        i += 1
    return "".join(out)


def inline_md(s: str, refs: bool = True) -> str:
    t = parser.parse(s)
    assert len(t) == 3, (s, t)
    return inlines(t[1].children, refs)


def visible(children: list[Token] | None) -> str:
    return "".join(
        c.content
        if c.type in ("text", "code_inline")
        else "\n"
        if c.type in ("softbreak", "hardbreak")
        else ""
        for c in children or []
    )


preamble = r"""% Additive source-synchronised revision. Build and inspection receipts are separate.
\documentclass[12pt,a4paper]{article}
\usepackage{fontspec}
\setmainfont{Liberation Serif}
\setsansfont{Liberation Sans}
\setmonofont{DejaVu Sans Mono}[Scale=0.85]
\usepackage[left=30mm,right=25mm,top=25mm,bottom=25mm]{geometry}
\usepackage{amsmath,amssymb,amsthm}
\usepackage{graphicx}
\usepackage{array,booktabs,longtable,tabularx,xltabular}
\usepackage{caption}
\usepackage{algorithm}
\usepackage{fvextra}
\usepackage{xurl}
\usepackage{setspace,ragged2e,placeins,needspace}
\usepackage[hidelinks,unicode]{hyperref}
\newtheorem{proposition}{Proposition}
\renewcommand{\theHtable}{\thesection.\arabic{table}}
\newcolumntype{Y}{>{\RaggedRight\arraybackslash\hspace{0pt}}X}
\setcounter{secnumdepth}{2}
\setcounter{tocdepth}{2}
\captionsetup{font=small,labelfont=bf,justification=raggedright,singlelinecheck=false}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.45em}
\setlength{\emergencystretch}{2em}
\newcommand{\appendixsection}[2]{%
  \clearpage\refstepcounter{section}%
  \section*{Appendix \thesection. #2}%
  \addcontentsline{toc}{section}{Appendix \thesection. #2}%
  \label{#1}\setcounter{table}{0}%
}
\begin{document}
\pagenumbering{arabic}
\thispagestyle{empty}
\begin{center}
\vspace*{12mm}
{\Large\bfseries TITLE\par}
\vspace{18mm}
{\large S M Abdulla Al Mamun\par}
\vspace{12mm}
{\large The University of Manchester\par}
\vspace{8mm}
Master's dissertation\par
2026\par
\vspace{12mm}
Supervisor: Dr Sandra Sampaio\par
\end{center}
\vfill
\begin{tabular}{@{}ll@{}}
Award wording: & \rule{95mm}{0.3pt}\\[9pt]
Faculty and School: & \rule{95mm}{0.3pt}\\[9pt]
Student ID: & \rule{95mm}{0.3pt}
\end{tabular}
\clearpage
\tableofcontents
\vfill\noindent\textbf{Word count: WORDCOUNT.} References, appendices, captions and front matter
excluded; Abstract, table text and pseudocode included. The counting receipt records
tokenisation.\par
\clearpage
{\small\singlespacing
\listoffigures
\listoftables
}
\clearpage
\section*{Abbreviations}
\addcontentsline{toc}{section}{Abbreviations}
\begin{tabularx}{\textwidth}{@{}lX@{}}
CI & Confidence interval\\
CLI & Command-line interface\\
CPU & Central processing unit\\
DRL & Deep reinforcement learning\\
E0--E2d & Historical validation, scoping and dispatch study stages\\
E3 & Separate dynamic-resource campaign, not executed\\
EV & Electric vehicle\\
ITS & Intelligent transportation systems\\
JAX & Array-computing and automatic-differentiation framework\\
MAPPO & Multi-agent proximal policy optimisation\\
PPO & Proximal policy optimisation\\
RQ & Research question\\
RSU & Roadside unit\\
SoC & State of charge\\
SUMO & Simulation of Urban MObility\\
V2I / V2V & Vehicle-to-infrastructure / vehicle-to-vehicle\\
VEC & Vehicular edge computing\\
\end{tabularx}
\clearpage
\onehalfspacing\RaggedRight
"""
front_declaration = r"""
\clearpage
\section*{Declaration}
\addcontentsline{toc}{section}{Declaration}
DECLARATION_TEXT

\medskip
\textbf{Candidate declaration to be signed.} The contribution statement and declared assistance
accurately describe the work submitted, and all non-original material is acknowledged.\par
\medskip
Prior submission for another qualification (select and complete):\par
$\square$ None.\qquad $\square$ Portions specified below.\par
\rule{\textwidth}{0.3pt}\par
\rule{\textwidth}{0.3pt}\par
\bigskip
Signature: \rule{60mm}{0.3pt}\qquad Date: \rule{25mm}{0.3pt}
\clearpage
\section*{Copyright and intellectual property}
\addcontentsline{toc}{section}{Copyright and intellectual property}
Original text, third-party material, source code and research inputs retain their respective
rights and applicable University arrangements. Access to a private repository or research
dataset does not grant unrestricted redistribution rights. Reuse must respect the relevant
licences, permissions and contributor acknowledgements. The software, actor, traffic inputs and
evidence records are separately identified so that their ownership is not conflated with
authorship of this report.
\clearpage
\section*{Acknowledgements}
\addcontentsline{toc}{section}{Acknowledgements}
ACKNOWLEDGEMENTS_TEXT
\clearpage
"""
short_fig = {
    "1": "Experimental responsibility boundaries",
    "2": "Morning RSU coordinates",
    "3": "Offered-task lifecycle",
    "4": "Illustrative dispatch comparison",
    "5": "Four-draw morning replication",
    "6": "All eight joint-randomness blocks",
    "7": "TrafficTwin Streamlit interface",
    "8": "Morning RSU work distribution",
}
short_tab = {
    "1": "Closest-work comparison",
    "2": "Scenario identities and controls",
    "3": "Infrastructure conditions",
    "4": "Incident attainment",
    "5": "Morning primary replication",
    "6": "Morning paired contrasts",
    "7": "Eight-block simultaneous contrasts",
    "8": "Scheduler-only engineering trade-offs",
    "9": "Software components and gates",
    "10": "Validity limits",
    "11": "Objective verdicts",
    "B1": "Historical audit coverage",
    "B2": "Matched task transitions",
    "C1": "Adverse dispatch illustration",
    "C2": "Morning outcome accounting",
    "C3": "Type-level net changes",
    "D1": "Type outcomes",
    "E1": "All confirmation cells",
    "E2": "Eight paired effects",
}
# Academic front-matter prose has the same Markdown source as the body.
front_match = re.search(
    r"(?ms)^## Declaration\n\n(.*?)^## Acknowledgements\n\n(.*?)^## Abstract", md
)
assert front_match, "Markdown Declaration and Acknowledgements are required"
front_declaration = front_declaration.replace(
    "DECLARATION_TEXT", inline_md(front_match[1].strip())
).replace("ACKNOWLEDGEMENTS_TEXT", inline_md(front_match[2].strip()))
body_md = md[: front_match.start()] + "## Abstract" + md[front_match.end() :]
tokens = parser.parse(body_md)
body = []
blocks = []
i = 0
inrefs = False
appendices = False
pending_table = None
bibnums = []
figures = []
tables = []
equations = []
algorithms = []
fullproof = False


def emit(kind: str, original: str, latex: str) -> None:
    n = len(blocks) + 1
    body.append(
        f"% BEGIN SOURCE BLOCK {n:03d} {kind}\n" + latex + f"\n% END SOURCE BLOCK {n:03d}\n"
    )
    blocks.append({"id": n, "kind": kind, "source": original, "latex": latex})


while i < len(tokens):
    t = tokens[i]
    if t.type == "heading_open":
        if fullproof:
            emit("proof_close", "", r"\end{proof}")
            fullproof = False
        title = tokens[i + 1].content
        level = int(t.tag[1])
        i += 3
        if level == 1:
            preamble = preamble.replace("TITLE", inline_md(title, False))
            blocks.append(
                {"id": 0, "kind": "title", "source": title, "latex": inline_md(title, False)}
            )
            continue
        if title == "References":
            emit(
                "bibliography_open",
                title,
                (
                    "\\clearpage\\singlespacing\\addcontentsline{toc}{section}{Reference"
                    "s}\\begin{thebibliography}{99}"
                ),
            )
            inrefs = True
            continue
        if title.startswith("Appendix "):
            if inrefs:
                emit("bibliography_close", "", r"\end{thebibliography}")
                inrefs = False
            if not appendices:
                emit(
                    "appendix_open",
                    "",
                    r"\appendix" + "\n" + r"\renewcommand{\thetable}{\Alph{section}\arabic{table}}",
                )
                appendices = True
            m = re.fullmatch(r"Appendix ([A-E])\. (.*)", title)
            assert m
            emit(
                "heading",
                title,
                r"\appendixsection{app:" + m[1] + "}{" + inline_md(m[2], False) + "}",
            )
            continue
        if title == "Abstract":
            emit(
                "heading",
                title,
                (
                    "\\section*{Abstract}\\addcontentsline{toc}{section}{Abstract}\\phan"
                    "tomsection\\label{sec:abstract}"
                ),
            )
            continue
        if title == "1. Introduction":
            body.append(front_declaration)
        else:
            body.append(r"\FloatBarrier")
        if title.startswith(("3.5 ", "3.6 ", "4. Conclusion")):
            body.append(r"\clearpage")
        m = re.fullmatch(r"((?:[A-E]|\d+)(?:\.\d+)?)\.? (.+)", title)
        assert m, title
        emit(
            "heading",
            title,
            ("\\section" if level == 2 else "\\subsection")
            + "{"
            + inline_md(m[2], False)
            + "}"
            + r"\label{sec:"
            + m[1]
            + "}",
        )
        continue
    if t.type == "html_block":
        m = re.search(r'id="([^"]+)"', t.content)
        assert m
        if not m[1].startswith("ref-"):
            emit("anchor", "", r"\phantomsection\label{" + m[1] + "}")
        i += 1
        continue
    if t.type == "paragraph_open":
        q = tokens[i + 1]
        raw = q.content
        ch = q.children
        i += 3
        if raw.startswith(("S M Abdulla Al Mamun", "Master's dissertation", "Supervisor:")):
            continue
        anchor = re.match(r'^<a id="([^"]+)"></a>\s*', raw)
        if anchor:
            if not anchor[1].startswith("ref-"):
                emit("anchor", "", r"\phantomsection\label{" + anchor[1] + "}")
            raw = raw[anchor.end() :]
            ch = parser.parseInline(raw)[0].children
        if fullproof and raw.startswith("Zero work is allowed:"):
            emit("proof_close", "", r"\end{proof}")
            fullproof = False
        if raw.startswith("**Proof.** "):
            emit("proof_open", "Proof.", r"\begin{proof}")
            fullproof = True
            raw = raw[len("**Proof.** ") :]
            ch = parser.parseInline(raw)[0].children
        if any(c.type == "image" for c in ch):
            img = next(c for c in ch if c.type == "image")
            assert tokens[i].type == "paragraph_open"
            cap = tokens[i + 1].content
            m = re.fullmatch(r"\*Figure (\d+)\. (.*)\*", cap, re.S)
            assert m, cap
            i += 3
            num = m[1]
            asset = img.attrGet("src")
            figures.append({"number": num, "asset": asset, "caption": m[2], "alt": img.content})
            code = (
                "\\begin{figure}[htbp]\n\\centering\n"
                + r"\includegraphics[width=\linewidth,height=.57\textheight,keepaspectratio]{"
                + asset
                + "}\n"
                + r"\caption["
                + inline_md(short_fig[num], False)
                + "]{"
                + inline_md(m[2])
                + "}"
                + r"\label{fig:"
                + num
                + "}\n\\end{figure}"
            )
            emit("figure", raw + "\n" + cap, code)
            continue
        m = re.fullmatch(r"\*Table ([A-E]?\d+)\. (.*)\*", raw, re.S)
        if m:
            pending_table = (m[1], m[2], raw)
            continue
        if inrefs:
            m = re.match(r"^\[(\d+)\] ", raw)
            assert m, raw
            num = m[1]
            bibnums.append(num)
            emit(
                "bibliography_item",
                raw,
                r"\bibitem{ref" + num + "} " + inline_md(raw[m.end() :], False),
            )
            continue
        m = re.match(r"^\*\*\((C1|\d)\)\*\* ", raw)
        if m:
            num = int(m[1]) if m[1].isdigit() else m[1]
            equations.append({"number": num, "source": raw, "latex": eqmap[num]})
            emit("equation", raw, eqmap[num])
            continue
        m = re.match(r"^\*\*Proposition 1 \(([^)]+)\)\.\*\* ", raw)
        if m:
            code = (
                r"\begin{proposition}["
                + inline_md(m[1], False)
                + "]"
                + r"\label{prop:1}"
                + "\n"
                + inline_md(raw[m.end() :])
                + r"\end{proposition}"
            )
            emit("proposition", raw, code)
            continue
        if raw.startswith("**Proof sketch.** "):
            emit(
                "proof",
                raw,
                r"\begin{proof}[Proof sketch]"
                + "\n"
                + inline_md(raw[len("**Proof sketch.** ") :])
                + r"\end{proof}",
            )
            continue
        emit("paragraph", raw, inlines(ch, not raw.startswith("S M Abdulla Al Mamun")))
        continue
    if t.type == "table_open":
        assert pending_table
        num, cap, rawcap = pending_table
        pending_table = None
        i += 1
        rows = []
        rawrows = []
        row = []
        rawrow = []
        while tokens[i].type != "table_close":
            tt = tokens[i]
            if tt.type == "tr_open":
                row = []
                rawrow = []
            elif tt.type == "inline":
                row.append(inlines(tt.children))
                rawrow.append(tt.content)
            elif tt.type == "tr_close":
                rows.append(row)
                rawrows.append(rawrow)
            i += 1
        i += 1
        n = len(rows[0])
        assert all(len(row) == n for row in rows)
        header = " & ".join(rows[0]) + r" \\"
        code = (
            (r"\Needspace{14\baselineskip}" + "\n" if num == "4" else "")
            + "\\begingroup\n"
            + r"\singlespacing\footnotesize\setlength{\tabcolsep}{3pt}"
            + "\n"
            + r"\begin{xltabular}{\textwidth}{@{}"
            + "Y" * n
            + "@{}}\n"
            + r"\caption["
            + inline_md(short_tab[num], False)
            + "]{"
            + inline_md(cap)
            + "}"
            + r"\label{tab:"
            + num
            + r"} \\"
            + "\n"
            + r"\toprule"
            + "\n"
            + header
            + "\n"
            + r"\midrule\endfirsthead"
            + "\n"
            + r"\toprule"
            + "\n"
            + header
            + "\n"
            + r"\midrule\endhead"
            + "\n"
            + r"\bottomrule\endfoot"
            + "\n"
            + "\n".join(" & ".join(row) + r" \\" for row in rows[1:])
            + "\n"
            + r"\end{xltabular}"
            + "\n"
            + r"\endgroup"
        )
        tables.append({"number": num, "caption": cap, "rows": rawrows})
        emit("table", rawcap + "\n" + "\n".join("|".join(row) for row in rawrows), code)
        continue
    if t.type == "fence":
        line, rest = t.content.rstrip("\n").split("\n", 1)
        m = re.fullmatch(r"Algorithm ([12]): (.*)", line)
        assert m
        num = m[1]
        algorithms.append({"number": num, "title": m[2], "body": rest})
        code = (
            "\\begin{algorithm}[htbp]\n"
            + r"\caption{"
            + inline_md(m[2], False)
            + "}"
            + r"\label{alg:"
            + num
            + "}\n"
            + r"\begin{Verbatim}[fontsize=\small,breaklines=true]"
            + "\n"
            + rest
            + "\n"
            + r"\end{Verbatim}"
            + "\n"
            + r"\end{algorithm}"
        )
        emit("algorithm", t.content, code)
        i += 1
        continue
    raise ValueError(("unexpected block", i, t.type, t.content))
assert bibnums == [str(i) for i in range(1, 26)]
counted = []
prose_counted = []
for block in blocks:
    if block["kind"] == "heading" and block["source"] == "References":
        break
    if block["kind"] == "bibliography_open":
        break
    if block["kind"] in (
        "paragraph",
        "heading",
        "proposition",
        "proof",
        "equation",
        "algorithm",
        "table",
    ):
        text = block["source"]
        if block["kind"] == "table":
            text = text.split("\n", 1)[1]
        for token in parser.parse(text):
            if token.type == "inline":
                counted.append(visible(token.children))
                if block["kind"] not in ("table", "algorithm"):
                    prose_counted.append(visible(token.children))
            elif token.type == "fence":
                counted.append(token.content)
words = len(re.findall(r"[\w]+(?:[’'-][\w]+)*", " ".join(counted)))
prose_words = len(re.findall(r"[\w]+(?:[’'-][\w]+)*", " ".join(prose_counted)))
(OUT / "document/WORD_COUNT.json").write_text(
    json.dumps(
        {
            "words": words,
            "prose_only_words": prose_words,
            "prose_only_method": (
                "Same tokenisation and boundaries as package method; "
                "additionally excludes table bodies and pseudocode"
            ),
            "method": (
                "Unicode word tokens; Abstract, main headings/body, table text, "
                "equations and pseudocode included; references, captions, "
                "appendices and front matter excluded"
            ),
        },
        indent=2,
    )
    + "\n"
)
preamble = preamble.replace("WORDCOUNT", f"{words:,}")
tex = preamble + "\n".join(body) + "\n\\end{document}\n"
(OUT / "TrafficTwin_Dissertation.tex").write_text(tex)
record = {
    "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
    "markdown_sha256": hashlib.sha256(md.encode()).hexdigest(),
    "tex_sha256": hashlib.sha256(tex.encode()).hexdigest(),
    "links_rebased": links,
    "blocks": blocks,
    "math_map": mathmap,
    "math_uses": mathuses,
    "equations": equations,
    "tables": tables,
    "figures": figures,
    "algorithms": algorithms,
    "bibkeys": ["ref" + n for n in bibnums],
    "refvalues": refvalues,
}
(OUT / "document/SOURCE_MAP.json").write_text(
    json.dumps(record, indent=2, ensure_ascii=False) + "\n"
)
print(
    json.dumps(
        {
            "blocks": len(blocks),
            "tables": len(tables),
            "figures": len(figures),
            "equations": len(equations),
            "algorithms": len(algorithms),
            "bibliography": len(bibnums),
            "output": str(OUT),
        },
        indent=2,
    )
)
