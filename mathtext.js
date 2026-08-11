/* Maths, written as maths.
 *
 * A model writes mathematics the way mathematicians type it: square roots
 * as a sqrt command, powers with a caret and braces, fractions as a frac
 * command, multiplication as a backslash word, and the whole expression
 * wrapped in dollars. None of that is readable to a class. This turns it
 * into what the same expression looks like on paper — real superscripts, a
 * stacked fraction, a root sign, the proper symbols.
 *
 * It lived inside index.html, which meant the WEBSITE rendered maths and
 * the classroom BOARD did not. The same lesson, on the screen thirty
 * children read from, showed the raw commands instead of the equation —
 * which is the whole of "the squares and the roots are missing".
 *
 * Shared here so the two cannot say different things about one lesson.
 * Plain globals on purpose: both pages already call mathText() by name.
 */
const MATH_SYM={
  times:"\u00d7",cdot:"\u00b7",div:"\u00f7",pm:"\u00b1",mp:"\u2213",
  leq:"\u2264",le:"\u2264",geq:"\u2265",ge:"\u2265",neq:"\u2260",ne:"\u2260",
  approx:"\u2248",equiv:"\u2261",sim:"\u223c",propto:"\u221d",
  infty:"\u221e",partial:"\u2202",nabla:"\u2207",
  sum:"\u2211",prod:"\u220f",int:"\u222b",oint:"\u222e",
  rightarrow:"\u2192",to:"\u2192",leftarrow:"\u2190",leftrightarrow:"\u2194",
  Rightarrow:"\u21d2",Leftrightarrow:"\u21d4",mapsto:"\u21a6",
  in:"\u2208",notin:"\u2209",subset:"\u2282",subseteq:"\u2286",
  cup:"\u222a",cap:"\u2229",emptyset:"\u2205",forall:"\u2200",exists:"\u2203",
  alpha:"\u03b1",beta:"\u03b2",gamma:"\u03b3",delta:"\u03b4",epsilon:"\u03b5",
  zeta:"\u03b6",eta:"\u03b7",theta:"\u03b8",lambda:"\u03bb",mu:"\u03bc",
  nu:"\u03bd",xi:"\u03be",pi:"\u03c0",rho:"\u03c1",sigma:"\u03c3",tau:"\u03c4",
  phi:"\u03c6",chi:"\u03c7",psi:"\u03c8",omega:"\u03c9",
  Gamma:"\u0393",Delta:"\u0394",Theta:"\u0398",Lambda:"\u039b",Pi:"\u03a0",
  Sigma:"\u03a3",Phi:"\u03a6",Psi:"\u03a8",Omega:"\u03a9",
  ldots:"\u2026",dots:"\u2026",cdots:"\u22ef",angle:"\u2220",degree:"\u00b0",
  circ:"\u00b0",perp:"\u22a5",parallel:"\u2225",therefore:"\u2234",
  because:"\u2235",sqrt:"\u221a"
};
const SUP={"0":"\u2070","1":"\u00b9","2":"\u00b2","3":"\u00b3","4":"\u2074",
  "5":"\u2075","6":"\u2076","7":"\u2077","8":"\u2078","9":"\u2079",
  "+":"\u207a","-":"\u207b","n":"\u207f","i":"\u2071"};
const SUB={"0":"\u2080","1":"\u2081","2":"\u2082","3":"\u2083","4":"\u2084",
  "5":"\u2085","6":"\u2086","7":"\u2087","8":"\u2088","9":"\u2089",
  "+":"\u208a","-":"\u208b"};

function mathText(html){
  let t=String(html==null?"":html);

  /* The delimiters go first. A model wraps maths in $...$, \(...\) or
     \[...\] and the wrapper carries no meaning for a reader. */
  t=t.replace(/\\\[|\\\]|\\\(|\\\)/g,"");

  /* $ is a delimiter and a currency symbol, and telling them apart is not
     optional: stripping both turned "profit is $3" into "profit is 3". So a
     $...$ pair is only unwrapped when what it contains actually looks like
     maths — a LaTeX command, a power, a subscript, or a short expression
     with no ordinary prose in it. Everything else keeps its dollars. */
  t=t.replace(/\$([^$\n]{1,200})\$/g,(m,inner)=>looksMathy(inner)?inner:m);

  /* \frac{a}{b} becomes a real stacked fraction — the one construction that
     genuinely cannot be written on a line without losing clarity. Nested
     twice, which covers everything short of a continued fraction. */
  const frac=/\\[dt]?frac\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}/g;
  for(let i=0;i<3;i++) t=t.replace(frac,
    (m,a,b)=>`<span class="mfrac"><span class="mnum">${a}</span>`
            +`<span class="mden">${b}</span></span>`);

  t=t.replace(/\\sqrt\s*\[([^\]]*)\]\s*\{([^{}]*)\}/g,"$1\u221a($2)");
  t=t.replace(/\\sqrt\s*\{([^{}]*)\}/g,"\u221a($1)");
  t=t.replace(/\\mathbb\s*\{([^{}]*)\}/g,
    (m,g)=>({R:"\u211d",N:"\u2115",Z:"\u2124",Q:"\u211a",C:"\u2102",
             P:"\u2119",H:"\u210d"}[g.trim()]||g));
  t=t.replace(/\\(?:text|mathrm|mathbf|mathit|mathsf|mathtt|mathcal|mathfrak|operatorname|boldsymbol)\s*\{([^{}]*)\}/g,"$1");
  t=t.replace(/\\left|\\right|\\,|\\;|\\!|\\quad|\\qquad/g," ");
  t=t.replace(/\\begin\{[^}]*\}|\\end\{[^}]*\}/g," ");

  /* Superscripts and subscripts as real characters where they exist, and as
     a styled span where they do not — x^{n+1} has no unicode form. */
  t=t.replace(/\^\s*\{([^{}]+)\}/g,(m,g)=>upDown(g,SUP,"msup"));
  t=t.replace(/\^\s*(-?[0-9a-zA-Z+])/g,(m,g)=>upDown(g,SUP,"msup"));
  t=t.replace(/_\s*\{([^{}]+)\}/g,(m,g)=>upDown(g,SUB,"msub"));
  t=t.replace(/_\s*(-?[0-9a-zA-Z+])/g,(m,g)=>upDown(g,SUB,"msub"));

  t=t.replace(/\\([A-Za-z]+)/g,(m,name)=>
    Object.prototype.hasOwnProperty.call(MATH_SYM,name)?MATH_SYM[name]:name);
  return t.replace(/\{|\}/g,"");
}

/* Is what sits between two dollar signs maths, or is it a sentence with
   prices in it? Anything with a backslash, a power or a subscript is maths
   outright. Otherwise it is maths only if it is short and free of ordinary
   words — "(ab + 1)" qualifies, "5 and profit is " does not. */
const MATH_WORDS=/^(sin|cos|tan|log|ln|exp|sqrt|max|min|lim|det|mod|and|or)$/;
function looksMathy(inner){
  // A LaTeX command, a power or a subscript settles it outright.
  if(/[\\^_]/.test(inner)) return true;
  // Otherwise, an opening "$" followed straight by a digit is money: prices,
  // salaries and revenues all look like that, and "$5 to $3 lakh" has no
  // three-letter word in it to give itself away. Real maths that starts with
  // a number nearly always carries a command or a power too, and that has
  // already been checked above.
  if(/^\d/.test(inner)) return false;
  if(inner.length>60) return false;
  // One ordinary word is enough. Keeping a dollar sign that was a delimiter
  // is untidy; removing one that was a price changes the number, so the
  // doubt is always resolved in favour of the money.
  const words=(inner.match(/[A-Za-z]{3,}/g)||[])
    .filter(w=>!MATH_WORDS.test(w.toLowerCase()));
  if(words.length>=1) return false;
  // A lone number between dollars is a price, not an equation.
  if(/^\s*-?[\d.,]+\s*$/.test(inner)) return false;
  return /[=+\-*/<>()]|[a-zA-Z]/.test(inner);
}

function upDown(txt,table,cls){
  const all=[...txt].every(c=>table[c]!==undefined);
  if(all) return [...txt].map(c=>table[c]).join("");
  return `<${cls==="msup"?"sup":"sub"}>${txt}</${cls==="msup"?"sup":"sub"}>`;
}
