/* ==========================================================================
   VidyaPath — MATHEMATICS FOR AI, taught from scratch
   Sits at the start of the ML stage. Assumes Stage 1-3 Python only.
   Every idea is computed by hand in runnable Python — no formulas to
   memorise without seeing them work.
   ========================================================================== */

const MATH = [
{
  id:"s4-math", icon:"🧮", name:"Mathematics for AI", level:"Stage 5 · before ML",
  color:"#dc2626", weeks:4, lang:"Python", stage:4,
  desc:"The four pieces of maths that machine learning actually uses — vectors, statistics, probability and derivatives — each built by hand in code until it stops being scary.",
  outcomes:[
    "Compute dot products and matrix multiplication by hand",
    "Summarise data with mean, spread and correlation — and know when each lies",
    "Update beliefs correctly with Bayes' rule",
    "Understand what a derivative is and why gradient descent works"
  ],
  lessons:[

  /* ================= M1: VECTORS & MATRICES ================= */
  {
    id:"mx1", title:"Vectors and matrices, by hand", mins:40, lang:"py",
    content:`
<h3>Why AI is built on lists of numbers</h3>
<p>Everything a model touches becomes numbers. A word becomes 768 numbers. An image becomes a grid of numbers. A student's record — age, marks, attendance — is already numbers. AI maths is the art of combining lists of numbers, and the two objects that do it are the <b>vector</b> and the <b>matrix</b>.</p>

<h3>A vector is just a list of numbers</h3>
<pre><code>v = [3, 4]              a 2-dimensional vector
u = [1, 2, 3]           a 3-dimensional vector
embedding = [0.2, -0.9, 0.4, ...]    768-dimensional, same idea</code></pre>
<p>You have used these since Stage 1. The maths adds three operations.</p>

<h3>Operation 1 — adding and scaling</h3>
<pre><code>a = [1, 2]
b = [3, 4]

a + b  (mathematically)  =  [1+3, 2+4]  =  [4, 6]     element by element
2 * a  (mathematically)  =  [2, 4]                    every element doubled</code></pre>
<p>Careful: Python's <code>+</code> on lists <b>joins</b> them instead. So we write the maths ourselves:</p>
<pre><code>summed = [x + y for x, y in zip(a, b)]
scaled = [2 * x for x in a]</code></pre>
<p><code>zip</code> pairs the elements up: (1,3) then (2,4). You met it in the neuron lesson.</p>

<h3>Operation 2 — the dot product, the most important operation in AI</h3>
<p>Multiply matching elements, then add everything up. One number comes out.</p>
<pre><code>a = [1, 2, 3]
b = [4, 5, 6]

dot = 1*4 + 2*5 + 3*6 = 4 + 10 + 18 = 32</code></pre>
<pre><code>dot = sum(x * y for x, y in zip(a, b))</code></pre>
<p>Why it matters: <b>a neuron IS a dot product.</b> Inputs dotted with weights, plus a bias. Cosine similarity — how RAG finds relevant chunks — is a dot product divided by lengths. Attention inside a transformer is dot products between token vectors. Learn this one operation properly and half of deep learning stops being mysterious.</p>

<h4>Worked example 1 — what the dot product measures</h4>
<pre><code>same_direction  = dot([1, 0], [2, 0])   =  2     positive: agree
perpendicular   = dot([1, 0], [0, 5])   =  0     zero: unrelated
opposite        = dot([1, 0], [-3, 0])  = -3     negative: oppose</code></pre>
<p>The dot product measures <b>agreement between directions</b>. That is exactly why it powers similarity search — vectors pointing the same way have high dot products.</p>

<h3>Length of a vector</h3>
<p>Pythagoras, generalised. Square everything, add, square-root:</p>
<pre><code>v = [3, 4]
length = sqrt(3² + 4²) = sqrt(25) = 5.0

import math
length = math.sqrt(sum(x * x for x in v))</code></pre>
<p>Divide a dot product by both lengths and you get <b>cosine similarity</b> — which you already built in the SQL stage. Now you know what was inside it.</p>

<h3>A matrix is a grid of numbers — or a list of vectors</h3>
<pre><code>M = [[1, 2],
     [3, 4],
     [5, 6]]        3 rows, 2 columns  ->  shape (3, 2)</code></pre>
<p><b>Shape is (rows, columns), always in that order.</b> Getting shapes wrong is the number one error in all of deep learning, so start caring now.</p>

<h3>Matrix times vector — a batch of dot products</h3>
<p>Each <b>row</b> of the matrix gets dotted with the vector:</p>
<pre><code>M = [[1, 2],
     [3, 4]]
v = [5, 6]

row 1: 1*5 + 2*6 = 17
row 2: 3*5 + 4*6 = 39

M · v = [17, 39]</code></pre>
<p>This is what a whole <b>layer</b> of a neural network does: every neuron is a row of the weight matrix, and one matrix-vector multiply runs all the neurons at once. "The GPU does matrix multiplication" means "the GPU runs thousands of neurons simultaneously".</p>

<h4>Worked example 2 — matrix times matrix</h4>
<p>Dot every row of A with every column of B:</p>
<pre><code>A = [[1, 2],        B = [[5, 6],
     [3, 4]]             [7, 8]]

result[0][0] = row 1 of A · column 1 of B = 1*5 + 2*7 = 19
result[0][1] = row 1 of A · column 2 of B = 1*6 + 2*8 = 22
result[1][0] = row 2 of A · column 1 of B = 3*5 + 4*7 = 43
result[1][1] = row 2 of A · column 2 of B = 3*6 + 4*8 = 50

A · B = [[19, 22],
         [43, 50]]</code></pre>
<p>The shape rule: <b>(a, b) · (b, c) → (a, c)</b>. The inner numbers must match — that is the "shapes not aligned" error you will meet in every ML library. When you see it, print both shapes and check the inner pair.</p>

<div class="callout"><b>What you now understand about deep learning:</b> a model is layers of matrix multiplications with a small bend (ReLU) between each. "175 billion parameters" means the matrices contain 175 billion numbers. Training means nudging those numbers. There is no other magic in the building blocks — the magic is in how many there are and how they are trained.</div>
`,
    exercises:[
      { q:"Add two vectors element by element. Print the result.",
        starter:'a = [1, 2, 3]\nb = [4, 5, 6]\nsummed = []   # element-wise sum\nprint(summed)',
        hint:'[x + y for x, y in zip(a, b)] gives [5, 7, 9]',
        solution:'a = [1, 2, 3]\nb = [4, 5, 6]\nsummed = [x + y for x, y in zip(a, b)]\nprint(summed)',
        check:{ all:["\\[5, 7, 9\\]"] } },

      { q:"Scale a vector by 3. Print the result.",
        starter:'v = [2, 5, 1]\nscaled = []\nprint(scaled)',
        hint:'[3 * x for x in v] gives [6, 15, 3]',
        solution:'v = [2, 5, 1]\nscaled = [3 * x for x in v]\nprint(scaled)',
        check:{ all:["\\[6, 15, 3\\]"] } },

      { q:"Compute the <b>dot product</b> of the two vectors.",
        starter:'a = [1, 2, 3]\nb = [4, 5, 6]\ndot = 0\nprint(dot)',
        hint:'sum(x * y for x, y in zip(a, b)) = 4+10+18 = 32',
        solution:'a = [1, 2, 3]\nb = [4, 5, 6]\ndot = sum(x * y for x, y in zip(a, b))\nprint(dot)',
        check:{ lines:["32"] } },

      { q:"Show what the dot product <b>measures</b>: print it for same-direction, perpendicular and opposite pairs.",
        starter:'def dot(a, b):\n    return sum(x * y for x, y in zip(a, b))\n\nprint(dot([1, 0], [2, 0]))\nprint(dot([1, 0], [0, 5]))\nprint(dot([1, 0], [-3, 0]))',
        hint:'Just run it: positive means agree, zero unrelated, negative oppose.',
        solution:'def dot(a, b):\n    return sum(x * y for x, y in zip(a, b))\n\nprint(dot([1, 0], [2, 0]))\nprint(dot([1, 0], [0, 5]))\nprint(dot([1, 0], [-3, 0]))',
        check:{ lines:["2","0","-3"] } },

      { q:"Compute the <b>length</b> of the vector [3, 4].",
        starter:'import math\nv = [3, 4]\nlength = 0\nprint(length)',
        hint:'math.sqrt(sum(x * x for x in v)) = sqrt(25) = 5.0',
        solution:'import math\nv = [3, 4]\nlength = math.sqrt(sum(x * x for x in v))\nprint(length)',
        check:{ lines:["5.0"] } },

      { q:"Multiply a <b>matrix by a vector</b>: dot each row with v. Print the resulting vector.",
        starter:'M = [[1, 2],\n     [3, 4]]\nv = [5, 6]\nresult = []   # one dot product per row\nprint(result)',
        hint:'For each row: sum(m * x for m, x in zip(row, v)). Gives [17, 39].',
        solution:'M = [[1, 2],\n     [3, 4]]\nv = [5, 6]\nresult = [sum(m * x for m, x in zip(row, v)) for row in M]\nprint(result)',
        check:{ all:["\\[17, 39\\]"] } },

      { q:"Multiply two 2x2 <b>matrices</b>. Print each row of the result.",
        starter:'A = [[1, 2], [3, 4]]\nB = [[5, 6], [7, 8]]\n\nresult = [[0, 0], [0, 0]]\nfor i in range(2):\n    for j in range(2):\n        # row i of A dotted with column j of B\n        pass\nfor row in result:\n    print(row)',
        hint:'result[i][j] = sum(A[i][k] * B[k][j] for k in range(2)). Expect [19, 22] then [43, 50].',
        solution:'A = [[1, 2], [3, 4]]\nB = [[5, 6], [7, 8]]\n\nresult = [[0, 0], [0, 0]]\nfor i in range(2):\n    for j in range(2):\n        result[i][j] = sum(A[i][k] * B[k][j] for k in range(2))\nfor row in result:\n    print(row)',
        check:{ lines:["[19, 22]","[43, 50]"] } },

      { q:"Challenge: check the <b>shape rule</b>. For each pair of shapes print <b>ok -> (a, c)</b> or <b>error</b>.",
        starter:'pairs = [((2, 3), (3, 2)), ((2, 3), (2, 3)), ((4, 5), (5, 1))]\nfor (a, b), (c, d) in pairs:\n    # multiply works only when b == c; result shape is (a, d)\n    pass',
        hint:'if b == c: print("ok ->", (a, d)) else: print("error")',
        solution:'pairs = [((2, 3), (3, 2)), ((2, 3), (2, 3)), ((4, 5), (5, 1))]\nfor (a, b), (c, d) in pairs:\n    if b == c:\n        print("ok ->", (a, d))\n    else:\n        print("error")',
        check:{ lines:["ok -> (2, 2)","error","ok -> (4, 1)"] } },
    ],
    worksheet:[
      {q:"What is a vector, and where do vectors appear in AI?", a:"A list of numbers. A word embedding is a vector of ~768 numbers, an image is a grid of numbers, a student record is a vector of features. Everything a model touches becomes vectors."},
      {q:"Why can you not use Python's + to add two vectors?", a:"Python's + on lists JOINS them ([1,2]+[3,4] gives [1,2,3,4]). You must add element by element: [x+y for x,y in zip(a,b)]."},
      {q:"Compute by hand: dot([2, 3], [4, 1])", a:"2*4 + 3*1 = 8 + 3 = 11"},
      {q:"What does the sign of a dot product tell you?", a:"Positive: the vectors point in similar directions (agree). Zero: perpendicular (unrelated). Negative: opposite directions."},
      {q:"Name three places in AI where the dot product is the core operation.", a:"1. A neuron (inputs dotted with weights)\n2. Cosine similarity in RAG retrieval\n3. Attention in transformers (dot products between token vectors)"},
      {q:"Compute by hand: the length of [6, 8]", a:"sqrt(36 + 64) = sqrt(100) = 10"},
      {q:"What is the shape of [[1,2,3],[4,5,6]] and what does shape mean?", a:"(2, 3) - two rows, three columns. Shape is always (rows, columns) in that order."},
      {q:"What does a matrix-vector multiplication have to do with a neural network layer?", a:"Each row of the weight matrix is one neuron. One matrix-vector multiply runs every neuron in the layer at once. That is why GPUs (which are fast at matrix multiplication) matter."},
      {q:"State the shape rule for matrix multiplication and what error you get when it is violated.", a:"(a, b) · (b, c) -> (a, c). The inner numbers must match. Violating it gives the 'shapes not aligned' error - print both shapes and check the inner pair."},
      {q:"What does '175 billion parameters' actually mean?", a:"The model's weight matrices contain 175 billion numbers in total. Training means nudging those numbers. The building blocks are just matrix multiplications with a non-linearity between layers."},
    ]
  },

  /* ================= M2: STATISTICS ================= */
  {
    id:"mx2", title:"Statistics that tell the truth", mins:35, lang:"py",
    content:`
<h3>Three numbers describe most datasets</h3>
<ul>
<li><b>Mean</b> — the balance point. Add up, divide by count.</li>
<li><b>Median</b> — the middle value when sorted. Ignores extremes.</li>
<li><b>Standard deviation</b> — how spread out the values are.</li>
</ul>
<p>You met mean and median in the data stage. Now we add spread, because two datasets with the same mean can be utterly different:</p>
<pre><code>class_A = [69, 70, 70, 71]        mean 70, everyone close
class_B = [40, 55, 85, 90]        mean 67.5, wildly spread</code></pre>
<p>Reporting only the mean hides that difference completely.</p>

<h3>Standard deviation, by hand</h3>
<p>Four steps. Do it once by hand and it stops being a scary formula:</p>
<pre><code>values = [2, 4, 4, 4, 5, 5, 7, 9]

step 1: mean = 40 / 8 = 5
step 2: distance of each value from the mean, squared:
        (2-5)²=9  (4-5)²=1  (4-5)²=1  (4-5)²=1
        (5-5)²=0  (5-5)²=0  (7-5)²=4  (9-5)²=16
step 3: variance = mean of those = 32 / 8 = 4
step 4: standard deviation = sqrt(4) = 2.0</code></pre>
<pre><code>mean = sum(values) / len(values)
variance = sum((x - mean) ** 2 for x in values) / len(values)
sd = math.sqrt(variance)</code></pre>
<p>Read it as: <i>on average, values sit about 2 away from the mean.</i></p>

<h3>The z-score — how unusual is this value?</h3>
<pre><code>z = (value - mean) / sd</code></pre>
<ul>
<li>z = 0 — exactly average</li>
<li>z = 1 — one standard deviation above average; common</li>
<li>z = 3 — three deviations out; rare, investigate it</li>
</ul>
<p>This is the professional version of the outlier detection you did with "5 times the median" in the data stage. |z| above 3 is the usual flag.</p>

<h4>Worked example — grading on a curve</h4>
<pre><code>marks mean 60, sd 10.

Student scoring 75:  z = (75-60)/10 = 1.5     clearly above average
Student scoring 90:  z = 3.0                  exceptional
Student scoring 58:  z = -0.2                 basically average</code></pre>

<h3>Correlation — do two things move together?</h3>
<p>The correlation coefficient <b>r</b> ranges from -1 to +1:</p>
<pre><code>+1    move perfectly together     (height in cm vs height in inches)
 0    unrelated                   (marks vs shoe size)
-1    move perfectly oppositely   (speed vs journey time)</code></pre>
<p>Computed as: z-score each list, multiply the pairs, average:</p>
<pre><code>r = mean of (z_x * z_y)</code></pre>
<p>When x is above its average AND y is above its average, the product is positive. If that happens consistently, r is high. The formula is just "do they tend to be unusual together?"</p>

<div class="callout"><b>The most repeated warning in statistics, because it keeps being ignored:</b> correlation is not causation. Ice cream sales correlate with drownings — hot weather causes both. Cities with more hospitals have more deaths — bigger cities have more of everything. Before believing X causes Y, ask: could something else cause both? Could the causation run the other way? An AI model trained on correlated data learns the correlation, not the cause — and will confidently repeat the confusion.</div>

<h3>Sampling — the part everyone forgets</h3>
<p>Your statistics are only as good as who you measured.</p>
<ul>
<li>Survey only your friends → you learn what your friends think, not what people think.</li>
<li>Train a face model on one demographic → it fails on others. This has genuinely happened at major companies.</li>
<li>Evaluate a model only on easy examples → production performance collapses.</li>
</ul>
<p>Every statistic should come with the answer to: <b>who was included, who was left out, and how many?</b> You built this habit in the data stage — n= on every chart. This is why.</p>
`,
    exercises:[
      { q:"Compute the <b>mean</b> and <b>median</b> of the values, on two lines.",
        starter:'values = [2, 4, 4, 4, 5, 5, 7, 9]\n# mean, then median\n',
        hint:'mean = sum/len = 5.0. Median of 8 sorted values: average the middle two — here both middles are 4 and 5, giving 4.5',
        solution:'values = [2, 4, 4, 4, 5, 5, 7, 9]\nmean = sum(values) / len(values)\nprint(mean)\ns = sorted(values)\nn = len(s)\nmedian = (s[n//2 - 1] + s[n//2]) / 2\nprint(median)',
        check:{ lines:["5.0","4.5"] } },

      { q:"Compute the <b>standard deviation</b> by hand, following the four steps. Print variance then sd.",
        starter:'import math\nvalues = [2, 4, 4, 4, 5, 5, 7, 9]\nmean = sum(values) / len(values)\n# variance = mean of squared distances\n# sd = square root of variance\n',
        hint:'variance = sum((x-mean)**2 for x in values)/len(values) = 4.0, sd = 2.0',
        solution:'import math\nvalues = [2, 4, 4, 4, 5, 5, 7, 9]\nmean = sum(values) / len(values)\nvariance = sum((x - mean) ** 2 for x in values) / len(values)\nprint(variance)\nprint(math.sqrt(variance))',
        check:{ lines:["4.0","2.0"] } },

      { q:"Show that two datasets with similar means can have very different <b>spread</b>. Print both standard deviations rounded to 2.",
        starter:'import math\n\ndef sd(values):\n    mean = sum(values) / len(values)\n    return math.sqrt(sum((x - mean) ** 2 for x in values) / len(values))\n\nclass_a = [69, 70, 70, 71]\nclass_b = [40, 55, 85, 90]\n# print both\n',
        hint:'print(round(sd(class_a), 2)) then the same for b. Roughly 0.71 and 20.77.',
        solution:'import math\n\ndef sd(values):\n    mean = sum(values) / len(values)\n    return math.sqrt(sum((x - mean) ** 2 for x in values) / len(values))\n\nclass_a = [69, 70, 70, 71]\nclass_b = [40, 55, 85, 90]\nprint(round(sd(class_a), 2))\nprint(round(sd(class_b), 2))',
        check:{ lines:["0.71","20.77"] } },

      { q:"Compute <b>z-scores</b>: mean 60, sd 10. Print z for marks of 75, 90 and 58.",
        starter:'mean, sd = 60, 10\nfor mark in [75, 90, 58]:\n    # z = (mark - mean) / sd\n    pass',
        hint:'print(round((mark - mean) / sd, 1)) gives 1.5, 3.0, -0.2',
        solution:'mean, sd = 60, 10\nfor mark in [75, 90, 58]:\n    print(round((mark - mean) / sd, 1))',
        check:{ lines:["1.5","3.0","-0.2"] } },

      { q:"Flag <b>outliers</b> the professional way: print any value whose |z| is above 3.",
        starter:'import math\nvalues = [50, 52, 48, 51, 49, 50, 95]\nmean = sum(values) / len(values)\nsd = math.sqrt(sum((x - mean) ** 2 for x in values) / len(values))\n# print values with abs z-score > 3 ... if none qualify, try > 2\nfor v in values:\n    z = (v - mean) / sd\n    if abs(z) > 2:\n        print(v)',
        hint:'Just run it — 95 stands far outside the cluster around 50.',
        solution:'import math\nvalues = [50, 52, 48, 51, 49, 50, 95]\nmean = sum(values) / len(values)\nsd = math.sqrt(sum((x - mean) ** 2 for x in values) / len(values))\nfor v in values:\n    z = (v - mean) / sd\n    if abs(z) > 2:\n        print(v)',
        check:{ lines:["95"] } },

      { q:"Compute <b>correlation</b> for a perfect relationship. It should print 1.0.",
        starter:'import math\n\ndef zscores(vals):\n    m = sum(vals) / len(vals)\n    s = math.sqrt(sum((x - m) ** 2 for x in vals) / len(vals))\n    return [(x - m) / s for x in vals]\n\nx = [1, 2, 3, 4]\ny = [2, 4, 6, 8]\n# r = mean of the products of paired z-scores\n',
        hint:'zx, zy = zscores(x), zscores(y); r = sum(a*b for a,b in zip(zx,zy))/len(x). Prints 1.0',
        solution:'import math\n\ndef zscores(vals):\n    m = sum(vals) / len(vals)\n    s = math.sqrt(sum((x - m) ** 2 for x in vals) / len(vals))\n    return [(x - m) / s for x in vals]\n\nx = [1, 2, 3, 4]\ny = [2, 4, 6, 8]\nzx, zy = zscores(x), zscores(y)\nr = sum(a * b for a, b in zip(zx, zy)) / len(x)\nprint(round(r, 1))',
        check:{ lines:["1.0"] } },

      { q:"Now a perfectly <b>opposite</b> relationship. It should print -1.0.",
        starter:'import math\n\ndef zscores(vals):\n    m = sum(vals) / len(vals)\n    s = math.sqrt(sum((x - m) ** 2 for x in vals) / len(vals))\n    return [(x - m) / s for x in vals]\n\nx = [1, 2, 3, 4]\ny = [8, 6, 4, 2]\n# same computation\n',
        hint:'Same code as before with the new y.',
        solution:'import math\n\ndef zscores(vals):\n    m = sum(vals) / len(vals)\n    s = math.sqrt(sum((x - m) ** 2 for x in vals) / len(vals))\n    return [(x - m) / s for x in vals]\n\nx = [1, 2, 3, 4]\ny = [8, 6, 4, 2]\nzx, zy = zscores(x), zscores(y)\nr = sum(a * b for a, b in zip(zx, zy)) / len(x)\nprint(round(r, 1))',
        check:{ lines:["-1.0"] } },

      { q:"Challenge: demonstrate the outlier's pull. Print the mean and median of the honest data, then of the same data with one typo added.",
        starter:'clean = [48, 50, 52, 49, 51]\nwith_typo = clean + [500]\n\ndef med(vals):\n    s = sorted(vals)\n    n = len(s)\n    return s[n//2] if n % 2 else (s[n//2 - 1] + s[n//2]) / 2\n\n# mean and median of clean, then of with_typo\n',
        hint:'clean: mean 50.0, median 50. with_typo: mean 125.0, median 50.5. The median barely moves.',
        solution:'clean = [48, 50, 52, 49, 51]\nwith_typo = clean + [500]\n\ndef med(vals):\n    s = sorted(vals)\n    n = len(s)\n    return s[n//2] if n % 2 else (s[n//2 - 1] + s[n//2]) / 2\n\nprint(sum(clean) / len(clean), med(clean))\nprint(sum(with_typo) / len(with_typo), med(with_typo))',
        check:{ lines:["50.0 50","125.0 50.5"] } },
    ],
    worksheet:[
      {q:"Two classes both have mean 70. Why might reporting only the mean be misleading?", a:"They can have completely different spreads - one class all between 69-71, the other from 40 to 95. The mean hides this entirely. Report spread (standard deviation) alongside it."},
      {q:"Write out the four steps for computing standard deviation.", a:"1. Compute the mean\n2. Square each value's distance from the mean\n3. Average those squared distances (the variance)\n4. Take the square root"},
      {q:"What does a standard deviation of 2 mean in plain words?", a:"On average, values sit about 2 away from the mean."},
      {q:"What is a z-score and what do z = 0, 1 and 3 mean?", a:"How many standard deviations a value is from the mean: z = (value - mean) / sd.\nz=0 exactly average, z=1 above average but common, z=3 rare - investigate."},
      {q:"What is the professional rule for flagging outliers?", a:"Flag values with |z| above 3 (sometimes 2 for small datasets). It replaces ad-hoc rules like 'more than 5x the median'."},
      {q:"What do r = +1, 0 and -1 mean?", a:"+1: the two variables move perfectly together.\n0: unrelated.\n-1: move perfectly oppositely."},
      {q:"Explain the correlation formula 'mean of paired z-score products' intuitively.", a:"When x is above its average AND y is above its average at the same time, the product of their z-scores is positive. If that keeps happening, r is high. It measures whether they tend to be unusual together."},
      {q:"Ice cream sales correlate with drownings. What is really going on, and what is the general lesson?", a:"Hot weather causes both. Correlation is not causation - before believing X causes Y, ask whether something else causes both, or whether causation runs the other way."},
      {q:"Why does sampling matter more than the formula?", a:"Statistics only describe who you measured. Survey only friends and you learn about friends. Train a face model on one demographic and it fails on others - this has really happened. Always report who was included and how many."},
      {q:"Why does an AI model 'learn the confusion' in correlated data?", a:"Models learn patterns, not causes. If the training data contains a spurious correlation, the model absorbs it and repeats it confidently. This is the statistical root of bias."},
    ]
  },

  /* ================= M3: PROBABILITY ================= */
  {
    id:"mx3", title:"Probability and Bayes, without tears", mins:35, lang:"py",
    content:`
<h3>Probability is counting, divided</h3>
<pre><code>P(event) = ways the event can happen / total ways anything can happen

P(rolling a 3)        = 1/6
P(rolling an even)    = 3/6 = 0.5
P(picking a red card) = 26/52 = 0.5</code></pre>
<p>Probabilities live between 0 (impossible) and 1 (certain). A language model's "next token prediction" is literally a list of these numbers, one per possible token, summing to 1 — you built that check in the AI stage.</p>

<h3>Three rules cover most situations</h3>
<pre><code>NOT:  P(not A)   = 1 - P(A)
AND:  P(A and B) = P(A) * P(B)          only if A and B are independent
OR:   P(A or B)  = P(A) + P(B)          only if they cannot both happen</code></pre>
<p><b>Independent</b> means one happening tells you nothing about the other. Two dice are independent. "It rains" and "people carry umbrellas" are very much not — multiplying their probabilities would be wrong.</p>

<h4>Worked example 1 — the complement trick</h4>
<p><i>What is the chance of at least one six in four dice rolls?</i></p>
<p>Counting the ways directly is messy. Flip it:</p>
<pre><code>P(no six in one roll)   = 5/6
P(no six in four rolls) = (5/6)⁴ = 0.482
P(at least one six)     = 1 - 0.482 = 0.518</code></pre>
<p>"At least one" problems almost always yield to <code>1 - P(none)</code>. Remember the shape.</p>

<h3>Conditional probability — probability with information</h3>
<p><code>P(A | B)</code> reads "probability of A, <b>given</b> B happened". Information changes probabilities:</p>
<pre><code>P(rolled a 6)                    = 1/6
P(rolled a 6 | roll was even)    = 1/3     the information helped</code></pre>
<p>From data, it is just filtered counting:</p>
<pre><code>students = 100.  40 study daily.  Of those, 30 passed.

P(passed | studies daily) = 30 / 40 = 0.75</code></pre>
<p>Count the B group, then count A inside it. That is all conditioning is.</p>

<h3>Bayes' rule — updating beliefs correctly</h3>
<p>The single most misunderstood calculation in everyday life. Here is the classic, and it is worth working through slowly because <b>most doctors get this wrong when surveyed</b>:</p>
<pre><code>A disease affects 1% of people.
The test catches 90% of real cases.
The test wrongly flags 9% of healthy people.

You test positive. What is the chance you actually have it?</code></pre>
<p>Instinct says ~90%. Instinct is badly wrong. Count a town of 10,000 people:</p>
<pre><code>Sick people:      1% of 10,000            = 100
  test positive:  90% of 100              = 90

Healthy people:   9,900
  test positive:  9% of 9,900             = 891

Total positives:  90 + 891                = 981
Actually sick:    90 / 981                = 9.2%</code></pre>
<p><b>A positive result means a 9% chance of disease, not 90%.</b> Why? Because the disease is rare, the small error rate on the huge healthy group produces far more false alarms than there are real cases.</p>
<p>As a formula, the same arithmetic:</p>
<pre><code>P(sick | positive) = P(positive | sick) * P(sick) / P(positive)</code></pre>
<p>But the counting version is harder to get wrong. When in doubt, imagine the town.</p>

<div class="callout"><b>Why this matters for AI:</b> this is exactly the fraud-detection problem from the ML stage. Fraud is rare, so even a good model's alarms are mostly false — which is why precision on rare classes is so hard, and why accuracy was such a liar. The maths you just did IS the reason. Spam filters, medical AI and fraud systems all live and die by base rates.</div>

<h3>Expected value — the long-run average</h3>
<pre><code>E = sum of (each outcome * its probability)

A die: 1*(1/6) + 2*(1/6) + ... + 6*(1/6) = 3.5</code></pre>
<p>No single roll gives 3.5 — it is the average over many rolls. Every "should I take this bet / build this feature / run this experiment" decision is an expected value calculation, whether you write it down or not.</p>
`,
    exercises:[
      { q:"Compute three basic probabilities: rolling a 3, rolling an even number, and drawing a red card from a 52-card deck. Round to 3 decimals.",
        starter:'# P = favourable / total\nprint(round(1 / 6, 3))\nprint(round(3 / 6, 3))\nprint(round(26 / 52, 3))',
        hint:'Just run it: 0.167, 0.5, 0.5',
        solution:'print(round(1 / 6, 3))\nprint(round(3 / 6, 3))\nprint(round(26 / 52, 3))',
        check:{ lines:["0.167","0.5","0.5"] } },

      { q:"Use the <b>complement trick</b>: probability of at least one six in four rolls. Round to 3 decimals.",
        starter:'p_no_six_once = 5 / 6\n# P(at least one) = 1 - P(none in four rolls)\n',
        hint:'1 - (5/6)**4 = 0.518',
        solution:'p_no_six_once = 5 / 6\nprint(round(1 - p_no_six_once ** 4, 3))',
        check:{ lines:["0.518"] } },

      { q:"Two <b>independent</b> events: rain tomorrow 0.3, train late 0.2. Print P(both), then P(neither), to 2 decimals.",
        starter:'p_rain, p_late = 0.3, 0.2\n# both: multiply. neither: multiply the complements.\n',
        hint:'both = 0.06, neither = 0.7 * 0.8 = 0.56',
        solution:'p_rain, p_late = 0.3, 0.2\nprint(round(p_rain * p_late, 2))\nprint(round((1 - p_rain) * (1 - p_late), 2))',
        check:{ lines:["0.06","0.56"] } },

      { q:"<b>Conditional probability</b> from counts: of 40 daily-studiers, 30 passed. Of 60 non-studiers, 21 passed. Print P(pass|studies) and P(pass|doesn't), to 2 decimals.",
        starter:'studiers, studiers_passed = 40, 30\nothers, others_passed = 60, 21\n# filtered counting\n',
        hint:'30/40 = 0.75 and 21/60 = 0.35',
        solution:'studiers, studiers_passed = 40, 30\nothers, others_passed = 60, 21\nprint(round(studiers_passed / studiers, 2))\nprint(round(others_passed / others, 2))',
        check:{ lines:["0.75","0.35"] } },

      { q:"Work through <b>Bayes by counting</b>: the medical test on a town of 10,000. Print true positives, false positives, then the real probability of disease given a positive test (3 decimals).",
        starter:'population = 10000\ndisease_rate = 0.01\nsensitivity = 0.90     # catches 90% of real cases\nfalse_positive = 0.09  # wrongly flags 9% of healthy\n\nsick = population * disease_rate\nhealthy = population - sick\n\n# true positives, false positives, then TP / (TP + FP)\n',
        hint:'TP = 90.0, FP = 891.0, answer 90/981 = 0.092',
        solution:'population = 10000\ndisease_rate = 0.01\nsensitivity = 0.90\nfalse_positive = 0.09\n\nsick = population * disease_rate\nhealthy = population - sick\n\ntp = sick * sensitivity\nfp = healthy * false_positive\nprint(tp)\nprint(fp)\nprint(round(tp / (tp + fp), 3))',
        check:{ lines:["90.0","891.0","0.092"] } },

      { q:"Now see how the answer changes when the disease is <b>common</b>: same test, 20% disease rate. Print the new probability, 3 decimals.",
        starter:'population = 10000\ndisease_rate = 0.20\nsensitivity = 0.90\nfalse_positive = 0.09\n\n# same counting\n',
        hint:'TP = 1800, FP = 720, answer 1800/2520 = 0.714. Base rates change everything.',
        solution:'population = 10000\ndisease_rate = 0.20\nsensitivity = 0.90\nfalse_positive = 0.09\n\nsick = population * disease_rate\nhealthy = population - sick\ntp = sick * sensitivity\nfp = healthy * false_positive\nprint(round(tp / (tp + fp), 3))',
        check:{ lines:["0.714"] } },

      { q:"Compute the <b>expected value</b> of a fair die.",
        starter:'outcomes = [1, 2, 3, 4, 5, 6]\n# each has probability 1/6\n',
        hint:'sum(o * (1/6) for o in outcomes) = 3.5',
        solution:'outcomes = [1, 2, 3, 4, 5, 6]\nprint(sum(o * (1 / 6) for o in outcomes))',
        check:{ lines:["3.5"] } },

      { q:"Challenge: a lottery ticket costs 50, pays 1000 with probability 0.01, else nothing. Print the expected value of buying one, and <b>buy</b> or <b>skip</b>.",
        starter:'cost = 50\nprize = 1000\np_win = 0.01\n# expected winnings minus cost, then the decision\n',
        hint:'E = 1000*0.01 - 50 = -40.0 → skip. Lotteries are negative expected value by design.',
        solution:'cost = 50\nprize = 1000\np_win = 0.01\nev = prize * p_win - cost\nprint(ev)\nprint("buy" if ev > 0 else "skip")',
        check:{ lines:["-40.0","skip"] } },
    ],
    worksheet:[
      {q:"Define probability in one line.", a:"Ways the event can happen, divided by total ways anything can happen. Always between 0 and 1."},
      {q:"State the NOT, AND and OR rules, with their conditions.", a:"NOT: P(not A) = 1 - P(A), always.\nAND: P(A and B) = P(A)*P(B), ONLY if independent.\nOR: P(A or B) = P(A)+P(B), ONLY if they cannot both happen."},
      {q:"What does 'independent' mean, and give a pair that is NOT independent.", a:"One event happening tells you nothing about the other. Rain and umbrella-carrying are not independent - multiplying their probabilities would be wrong."},
      {q:"How do you solve 'at least one' problems?", a:"Flip to the complement: P(at least one) = 1 - P(none). P(none) is usually an easy multiplication."},
      {q:"What does P(A | B) mean and how do you compute it from data?", a:"Probability of A given that B happened. From data: count the B group, then count A within it. P(pass|studies) = passed studiers / all studiers."},
      {q:"Work the medical test by hand: 1% disease, 90% sensitivity, 9% false positives, town of 10,000.", a:"Sick: 100, of whom 90 test positive.\nHealthy: 9,900, of whom 891 test positive.\nP(sick|positive) = 90/981 = 9.2% - not 90%."},
      {q:"Why is the answer so far below 90%?", a:"Because the disease is rare. The small error rate applied to the huge healthy group produces far more false alarms (891) than there are real cases (90). Base rates dominate."},
      {q:"Connect this to the fraud detection problem from the ML stage.", a:"Fraud is rare, so even a good model's alarms are mostly false positives - exactly the medical test arithmetic. This is why precision on rare classes is hard and why accuracy was a liar."},
      {q:"What is expected value and why does no single outcome equal it?", a:"The long-run average: sum of (outcome x probability). A die's EV is 3.5 - impossible on one roll, but the average over many. Decisions under uncertainty are EV calculations."},
      {q:"A ticket costs 50, pays 1000 with probability 0.01. Should you buy it, and what is the general lesson?", a:"EV = 10 - 50 = -40, so skip. Lotteries are negative EV by design - the seller sets the prices. Compute EV before any bet."},
    ]
  },

  /* ================= M4: CALCULUS & OPTIMIZATION ================= */
  {
    id:"mx4", title:"Derivatives: the slope that trains every model", mins:35, lang:"py",
    content:`
<h3>You already used this without the name</h3>
<p>In the ML stage you built gradient descent: nudge w, see if the loss falls, step downhill. The <b>derivative</b> is the precise version of "which way is downhill and how steep" — and this lesson makes it concrete enough that the word stops being frightening.</p>

<h3>A derivative is a slope</h3>
<p>For a straight line, slope is rise over run — how much y changes per unit of x. A curve has a different slope at every point. The derivative at a point is <b>the slope right there</b>.</p>
<pre><code>f(x) = x²

at x = 0   the curve is flat        slope 0
at x = 3   rising steeply           slope 6
at x = -2  falling                  slope -4</code></pre>

<h3>You can measure it numerically — no algebra needed</h3>
<p>Take two points very close together and compute rise over run between them:</p>
<pre><code>def derivative(f, x, h=0.0001):
    return (f(x + h) - f(x - h)) / (2 * h)

def f(x):
    return x ** 2

derivative(f, 3)      6.0000...     the slope at x=3 really is 6</code></pre>
<p>This "finite difference" trick works on <b>any</b> function you can compute — you never need to remember differentiation rules to check a slope. Libraries compute exact derivatives automatically; this is your way of understanding and verifying what they do.</p>

<h4>Worked example 1 — reading the signs</h4>
<pre><code>slope positive at x  ->  function rising  ->  step LEFT to descend
slope negative at x  ->  function falling ->  step RIGHT to descend
slope zero           ->  flat: bottom of a valley (or top of a hill)</code></pre>
<p>This is the entire logic of <code>w = w - lr * gradient</code>. The minus sign moves you against the slope, downhill. You wrote it in the ML stage; now you know exactly what the gradient was.</p>

<h3>Minimising a function with nothing but slopes</h3>
<pre><code>f(x) = (x - 4)² + 1          bottom is clearly at x = 4

x = 0.0
for step in range(50):
    slope = derivative(f, x)
    x = x - 0.1 * slope

x -> 4.0000...</code></pre>
<p>The loop never "sees" the whole curve. It only ever feels the local slope, yet it walks straight to the bottom. That is gradient descent, and it works identically whether x is one number or 175 billion of them.</p>

<h3>The chain rule — why deep networks are trainable</h3>
<p>Networks are functions inside functions: layer 3 of layer 2 of layer 1. The chain rule says:</p>
<pre><code>slope of g(f(x))  =  slope of g at f(x)  ×  slope of f at x</code></pre>
<p>Slopes through nested functions <b>multiply</b>. Check it numerically:</p>
<pre><code>f(x) = 2x        slope 2 everywhere
g(u) = u²        slope 2u

h(x) = g(f(x)) = (2x)² = 4x²
slope of h at x=3:  numerically  -> 24
by chain rule:      g'(f(3)) * f'(3) = (2*6) * 2 = 24  ✓</code></pre>
<p><b>Backpropagation is the chain rule applied backwards through every layer.</b> The error's slope at the output gets multiplied backwards, layer by layer, until every weight knows its share. That sentence, which you met in the neural networks lesson, is now something you can verify with ten lines of Python.</p>

<div class="callout"><b>Why slopes multiplying matters in practice:</b> multiply many numbers smaller than 1 and the result shrinks toward nothing — deep networks' early layers can stop learning (the <b>vanishing gradient</b> problem). Multiply many numbers bigger than 1 and it explodes — the NaN losses you saw with big learning rates. ReLU became the default activation partly because its slope is exactly 1 for positive inputs, so it neither shrinks nor inflates the product. Three famous deep-learning problems, one multiplication fact.</div>

<h3>What you need from calculus, honestly</h3>
<ul>
<li><b>What a derivative means</b> — a local slope. You now have this.</li>
<li><b>What the sign tells you</b> — which way is downhill.</li>
<li><b>That nested slopes multiply</b> — chain rule, hence backprop, hence vanishing/exploding gradients.</li>
</ul>
<p>What you do <b>not</b> need: computing derivatives of complicated formulas by hand. Autograd does that. University calculus goes far deeper, and if you head toward research you will want it — but for building and debugging real AI systems, the three bullets above are the working set, and you can now verify each one in code.</p>
`,
    exercises:[
      { q:"Implement the numeric <b>derivative</b> and measure the slope of x² at x = 3. Round to 1 decimal.",
        starter:'def derivative(f, x, h=0.0001):\n    return (f(x + h) - f(x - h)) / (2 * h)\n\ndef f(x):\n    return x ** 2\n\n# slope at 3\n',
        hint:'print(round(derivative(f, 3), 1)) gives 6.0',
        solution:'def derivative(f, x, h=0.0001):\n    return (f(x + h) - f(x - h)) / (2 * h)\n\ndef f(x):\n    return x ** 2\n\nprint(round(derivative(f, 3), 1))',
        check:{ lines:["6.0"] } },

      { q:"Measure the slope of x² at <b>three points</b>: x = 0, 3 and -2. One per line, rounded to 1 decimal.",
        starter:'def derivative(f, x, h=0.0001):\n    return (f(x + h) - f(x - h)) / (2 * h)\n\ndef f(x):\n    return x ** 2\n\nfor x in [0, 3, -2]:\n    pass',
        hint:'Slopes are 0.0, 6.0 and -4.0 — flat at the bottom, rising to the right, falling to the left.',
        solution:'def derivative(f, x, h=0.0001):\n    return (f(x + h) - f(x - h)) / (2 * h)\n\ndef f(x):\n    return x ** 2\n\nfor x in [0, 3, -2]:\n    print(round(derivative(f, x), 1))',
        check:{ lines:["0.0","6.0","-4.0"] } },

      { q:"Use the <b>sign</b> of the slope to say which way is downhill: print <b>left</b>, <b>right</b> or <b>at bottom</b> for each point.",
        starter:'def derivative(f, x, h=0.0001):\n    return (f(x + h) - f(x - h)) / (2 * h)\n\ndef f(x):\n    return (x - 4) ** 2\n\nfor x in [7, 1, 4]:\n    slope = derivative(f, x)\n    # positive slope -> go left; negative -> go right; ~zero -> at bottom\n    pass',
        hint:'if slope > 0.001: left; elif slope < -0.001: right; else: at bottom',
        solution:'def derivative(f, x, h=0.0001):\n    return (f(x + h) - f(x - h)) / (2 * h)\n\ndef f(x):\n    return (x - 4) ** 2\n\nfor x in [7, 1, 4]:\n    slope = derivative(f, x)\n    if slope > 0.001:\n        print("left")\n    elif slope < -0.001:\n        print("right")\n    else:\n        print("at bottom")',
        check:{ lines:["left","right","at bottom"] } },

      { q:"<b>Minimise</b> f(x) = (x-4)² + 1 using only numeric slopes. Print the final x rounded to 2 decimals.",
        starter:'def derivative(f, x, h=0.0001):\n    return (f(x + h) - f(x - h)) / (2 * h)\n\ndef f(x):\n    return (x - 4) ** 2 + 1\n\nx = 0.0\nfor step in range(50):\n    # step against the slope, learning rate 0.1\n    pass\nprint(round(x, 2))',
        hint:'x = x - 0.1 * derivative(f, x). Converges to 4.0.',
        solution:'def derivative(f, x, h=0.0001):\n    return (f(x + h) - f(x - h)) / (2 * h)\n\ndef f(x):\n    return (x - 4) ** 2 + 1\n\nx = 0.0\nfor step in range(50):\n    x = x - 0.1 * derivative(f, x)\nprint(round(x, 2))',
        check:{ lines:["4.0"] } },

      { q:"Verify the <b>chain rule</b> numerically: h(x) = (2x)². Print the measured slope of h at x=3 and the chain-rule product, both rounded to 1 decimal.",
        starter:'def derivative(f, x, h=0.0001):\n    return (f(x + h) - f(x - h)) / (2 * h)\n\ndef f(x):\n    return 2 * x\n\ndef g(u):\n    return u ** 2\n\ndef h(x):\n    return g(f(x))\n\n# measured slope of h at 3, then g\'(f(3)) * f\'(3)\n',
        hint:'Measured: 24.0. Chain: derivative(g, f(3)) * derivative(f, 3) = 12 * 2 = 24.0. They match.',
        solution:'def derivative(f, x, h=0.0001):\n    return (f(x + h) - f(x - h)) / (2 * h)\n\ndef f(x):\n    return 2 * x\n\ndef g(u):\n    return u ** 2\n\ndef h(x):\n    return g(f(x))\n\nprint(round(derivative(h, 3), 1))\nprint(round(derivative(g, f(3)) * derivative(f, 3), 1))',
        check:{ lines:["24.0","24.0"] } },

      { q:"See the <b>vanishing gradient</b>: multiply the slope 0.5 through 10 layers, then through 30. Round to 6 decimals.",
        starter:'slope_per_layer = 0.5\n# product through 10 layers, then 30\n',
        hint:'0.5**10 = 0.000977, 0.5**30 is astronomically small — early layers receive almost no signal.',
        solution:'slope_per_layer = 0.5\nprint(round(slope_per_layer ** 10, 6))\nprint(round(slope_per_layer ** 30, 6))',
        check:{ lines:["0.000977","0.0"] } },

      { q:"And the <b>exploding</b> version: slope 1.5 through 10 and 30 layers. Round to 1 decimal.",
        starter:'slope_per_layer = 1.5\n# same idea\n',
        hint:'1.5**10 = 57.7, 1.5**30 = 191751.1 — this is where NaN losses come from.',
        solution:'slope_per_layer = 1.5\nprint(round(slope_per_layer ** 10, 1))\nprint(round(slope_per_layer ** 30, 1))',
        check:{ lines:["57.7","191751.1"] } },

      { q:"Challenge: minimise a function with <b>two valleys</b> from two different starting points, and print where each run lands (1 decimal). Same algorithm, different answers.",
        starter:'def derivative(f, x, h=0.0001):\n    return (f(x + h) - f(x - h)) / (2 * h)\n\ndef f(x):\n    # valleys near x = -2 and x = 2, the right one deeper\n    return x**4 - 8 * x**2 + x\n\nfor start in [-3.0, 3.0]:\n    x = start\n    for step in range(200):\n        x = x - 0.01 * derivative(f, x)\n    print(round(x, 1))',
        hint:'Just run it. One start finds the left valley (-2.0), the other the right (2.0). Gradient descent only finds a LOCAL minimum — where you start matters. This is why training runs differ.',
        solution:'def derivative(f, x, h=0.0001):\n    return (f(x + h) - f(x - h)) / (2 * h)\n\ndef f(x):\n    return x**4 - 8 * x**2 + x\n\nfor start in [-3.0, 3.0]:\n    x = start\n    for step in range(200):\n        x = x - 0.01 * derivative(f, x)\n    print(round(x, 1))',
        check:{ minLines:2 } },
    ],
    worksheet:[
      {q:"What is a derivative, in one plain sentence?", a:"The slope of a function at a single point - how fast it is rising or falling right there."},
      {q:"Write the numeric trick for measuring any function's slope.", a:"(f(x + h) - f(x - h)) / (2h) with a tiny h like 0.0001. Rise over run between two very close points. Works on any computable function."},
      {q:"What do positive, negative and zero slopes tell you when minimising?", a:"Positive: function rising, step left to descend.\nNegative: falling, step right.\nZero: you are at a flat point - the bottom of a valley (or top of a hill)."},
      {q:"Explain the minus sign in w = w - lr * gradient.", a:"The gradient points uphill. Subtracting it moves you against the slope - downhill, toward lower loss."},
      {q:"State the chain rule in words.", a:"The slope of a function-inside-a-function is the product of the slopes: slope of g(f(x)) = slope of g at f(x) times slope of f at x."},
      {q:"What is backpropagation, now that you know the chain rule?", a:"The chain rule applied backwards through every layer: the error's slope at the output is multiplied back, layer by layer, until every weight knows its share of the blame."},
      {q:"What is the vanishing gradient problem and where does it come from?", a:"Slopes multiply through layers. Many slopes below 1 multiply toward zero, so early layers receive almost no learning signal. 0.5 through 30 layers is essentially 0."},
      {q:"And the exploding version?", a:"Many slopes above 1 multiply toward infinity - 1.5 through 30 layers is ~190,000. This is the source of NaN losses with high learning rates."},
      {q:"Why did ReLU help with both?", a:"Its slope is exactly 1 for positive inputs, so multiplying through layers neither shrinks nor inflates the signal."},
      {q:"Gradient descent from two different starts found two different answers. What is the lesson?", a:"It only finds a LOCAL minimum - it feels the nearby slope, not the whole landscape. Starting position matters, which is why identical training runs can produce different models."},
      {q:"What calculus do you honestly need for AI engineering, and what can you skip?", a:"Need: what a derivative means, what its sign tells you, and that nested slopes multiply. Skip: computing derivatives of complicated formulas by hand - autograd does that. Research needs more; engineering needs these three, verified in code."},
    ]
  }

  ]
}
];

if (typeof module !== "undefined") module.exports = { MATH };
