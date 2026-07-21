/* ==========================================================================
   VidyaPath — SCHOOL CURRICULUM  (Class 8 to 12)
   Written for students aged 13-17 with zero computer knowledge.

   Every lesson is SELF-CONTAINED. No video needed. No outside reading needed.
   Structure of each lesson:
     content   — the full teaching notes, in plain everyday language
     exercises — 6 to 8 practice questions, easy to hard, auto-checked
     worksheet — printable questions for offline / classroom use
   Run:  node convert-school.js   →  school.json
   ========================================================================== */

const SCHOOL = [

/* =================================================================== */
/* TRACK 1 — FIRST STEPS                                               */
/* =================================================================== */
{
  id:"s-start", icon:"🌱", name:"First Steps with Computers", level:"Class 8-12 · Start here",
  color:"#3fb950", weeks:2, lang:"Python",
  desc:"You have never written a single line of code. That is exactly who this is for. By the end you will have made the computer do what YOU told it to do.",
  outcomes:[
    "Explain in your own words what a program is",
    "Write and run your first Python program",
    "Store information in variables and use it",
    "Ask the user a question and use their answer"
  ],
  lessons:[

  /* ---------------- LESSON 1 ---------------- */
  {
    id:"sc1", title:"What is a computer really doing?", mins:20, lang:"py",
    content:`
<h3>Let us start with something you already know</h3>
<p>Think about making tea. You follow steps:</p>
<pre><code>1. Boil water
2. Add tea leaves
3. Wait 3 minutes
4. Add milk and sugar
5. Pour into cup</code></pre>
<p>That list of steps is called a <b>recipe</b>. You follow it from top to bottom.</p>
<p>A computer program is exactly the same thing. It is a list of steps. The computer starts at the top and does each step, one after another, until it reaches the bottom.</p>
<p><b>That is it. That is what programming is.</b> Writing steps for the computer to follow.</p>

<h3>But the computer is very, very stupid</h3>
<p>This part surprises everybody. The computer is not clever. It is extremely fast, but it has no common sense at all.</p>
<p>If you tell a friend "make tea", they know what you mean. If you tell a computer "make tea", it has no idea. You must say every single step. If you forget "add water", the computer will happily try to boil an empty vessel.</p>
<div class="callout"><b>Remember this:</b> The computer does exactly what you say. Not what you meant. Almost every mistake you will ever make in programming comes from this one fact.</div>

<h3>The four things a computer can do</h3>
<p>Every program in the world — games, WhatsApp, YouTube, banking apps — is built from only four actions:</p>
<ul>
<li><b>Remember</b> something (store a number, a name, a score)</li>
<li><b>Compare</b> two things (is this bigger? are these the same?)</li>
<li><b>Repeat</b> something (do this 100 times)</li>
<li><b>Decide</b> what to do next based on a comparison</li>
</ul>
<p>Four things. That is the whole toolbox. Everything else is just these four combined in clever ways.</p>

<h3>The parts of a computer, in simple words</h3>
<ul>
<li><b>CPU</b> — the brain. It does the thinking, extremely fast. Millions of steps every second.</li>
<li><b>RAM</b> — the desk. Things you are working on right now sit here. <b>When you switch off, the desk is cleared completely.</b></li>
<li><b>Hard disk</b> — the cupboard. Things stored here stay even after switching off. Your photos and files live here.</li>
</ul>
<p>This is why you lose an unsaved document when the power goes. It was on the desk (RAM), never put in the cupboard (disk).</p>

<h3>What is Python?</h3>
<p>The computer only understands electricity — on and off, which we write as 1 and 0. Writing programs in 1s and 0s would be impossible for humans.</p>
<p>So we write in a <b>programming language</b> instead. It looks a bit like English. Then a translator turns it into 1s and 0s for the computer.</p>
<p><b>Python</b> is one such language. We chose it because it is the closest to plain English, and because it is what real engineers use to build Artificial Intelligence.</p>

<h3>Your very first instruction: print</h3>
<p><code>print</code> means "show this on the screen". It does not mean printing on paper.</p>

<h4>Worked example 1</h4>
<pre><code>print("Hello")</code></pre>
<p>Let us read this slowly, piece by piece:</p>
<ul>
<li><code>print</code> — the instruction. It says: show something.</li>
<li><code>(</code> and <code>)</code> — brackets. Whatever goes inside is what gets shown.</li>
<li><code>"Hello"</code> — the message. The double quotes tell Python "this is text, not an instruction".</li>
</ul>
<p>Output on screen:</p>
<pre><code>Hello</code></pre>

<h4>Worked example 2 — two lines</h4>
<pre><code>print("My name is Ravi")
print("I am learning Python")</code></pre>
<p>The computer starts at the top. It does line 1, shows the first message. Then it moves to line 2 and shows the second message.</p>
<p>Output:</p>
<pre><code>My name is Ravi
I am learning Python</code></pre>
<p>Each <code>print</code> starts a new line. You did not have to ask for that; it happens automatically.</p>

<h4>Worked example 3 — a common mistake</h4>
<pre><code>print(Hello)</code></pre>
<p>This gives an <b>error</b>. The quotes are missing. Without quotes, Python thinks <code>Hello</code> is the name of something you stored earlier. It looks for it, cannot find it, and complains.</p>
<p><b>Rule: text always goes inside quotes.</b></p>

<h3>Errors are completely normal</h3>
<p>You will see errors constantly. Every professional programmer sees errors many times a day, every day, for their whole career. An error is not failure. It is the computer telling you which line it did not understand. Read it, fix that line, run again.</p>
`,
    exercises:[
      { q:"Make the computer show the word <b>Namaste</b> on the screen.",
        starter:'print("")',
        hint:'Put the word Namaste inside the quotes: print("Namaste")',
        solution:'print("Namaste")',
        check:{ all:["^Namaste$"] } },

      { q:"Show your own name on the screen. Use any name you like.",
        starter:'# Write your print instruction below\n',
        hint:'print("Thirumal") — put any name inside the quotes.',
        solution:'print("Thirumal")',
        check:{ minLines:1 } },

      { q:"Show <b>two</b> lines: first <b>I am in school</b>, then <b>I am learning Python</b>.",
        starter:'print("I am in school")\n# add the second line below\n',
        hint:'You need two separate print instructions, one under the other.',
        solution:'print("I am in school")\nprint("I am learning Python")',
        check:{ lines:["I am in school","I am learning Python"] } },

      { q:"This code is broken. The quotes are missing. Fix it so it shows <b>Good morning</b>.",
        starter:'print(Good morning)',
        hint:'Text needs quotes around it. Put " before Good and after morning.',
        solution:'print("Good morning")',
        check:{ all:["^Good morning$"] } },

      { q:"Show these three lines in this exact order: <b>Ready</b>, then <b>Steady</b>, then <b>Go</b>.",
        starter:'# three print instructions, one below the other\n',
        hint:'Three separate lines, each with its own print.',
        solution:'print("Ready")\nprint("Steady")\nprint("Go")',
        check:{ lines:["Ready","Steady","Go"] } },

      { q:"The computer can do maths too. Numbers do <b>not</b> need quotes. Make it show the answer to 25 + 17.",
        starter:'print(25 + 17)',
        hint:'Just run it. Notice there are no quotes around the numbers.',
        solution:'print(25 + 17)',
        check:{ all:["^42$"] } },

      { q:"Now see the difference. Run this and look carefully at the two outputs.",
        starter:'print(10 + 5)\nprint("10 + 5")',
        hint:'Without quotes Python calculates. With quotes it just shows the text exactly.',
        solution:'print(10 + 5)\nprint("10 + 5")',
        check:{ lines:["15","10 + 5"] } },

      { q:"Challenge: show your school name, then on the next line show the answer to 144 divided by 12. Use / for divide.",
        starter:'# line 1: your school name in quotes\n# line 2: the division, no quotes\n',
        hint:'print("My School") then print(144 / 12). The answer will show as 12.0',
        solution:'print("My School")\nprint(144 / 12)',
        check:{ all:["12\\.0"], minLines:2 } },
    ],
    worksheet:[
      {q:"In your own words, what is a computer program?", a:"A list of steps that the computer follows one after another, from top to bottom. Like a recipe."},
      {q:"Why do we say the computer is 'stupid'?", a:"It has no common sense. It does exactly what you tell it, not what you meant. You must spell out every single step."},
      {q:"Name the four things every program is built from.", a:"Remember, Compare, Repeat, Decide."},
      {q:"You typed a long essay but did not save it, and the power went off. It is gone. Explain why, using the words RAM and hard disk.", a:"The essay was in RAM, which is like a desk that gets cleared when power goes off. It was never saved to the hard disk, which is like a cupboard that keeps things permanently."},
      {q:"What does print do?", a:"It shows something on the screen. It has nothing to do with printing on paper."},
      {q:"Write the code to show the word Welcome on screen.", a:'print("Welcome")'},
      {q:"What is wrong with this: print(Welcome)", a:"The quotes are missing. Text must be inside quotes. It should be print(\"Welcome\")"},
      {q:"What will these two lines show?\nprint(20 + 30)\nprint(\"20 + 30\")", a:"First line shows 50 because there are no quotes, so Python calculates it.\nSecond line shows 20 + 30 exactly as written, because quotes mean 'this is just text'."},
      {q:"A student says 'I got an error, so I am bad at programming.' What would you tell them?", a:"Errors are completely normal. Every professional programmer gets them many times a day. An error just tells you which line the computer did not understand. Read it, fix that line, try again."},
    ]
  },

  /* ---------------- LESSON 2 ---------------- */
  {
    id:"sc2", title:"Boxes that remember: variables", mins:25, lang:"py",
    content:`
<h3>The problem</h3>
<p>Say you are writing a program about a student called Anjali. You write her name in ten different places. Then you need to change it to Bhavna. Now you must find and fix all ten places. Miss one, and your program is wrong.</p>
<p>There is a better way.</p>

<h3>A variable is a labelled box</h3>
<p>Imagine a box. You put something inside it. You stick a label on the front. Later, whenever you say the label, you get whatever is inside.</p>
<pre><code>name = "Anjali"</code></pre>
<p>Read this from right to left, like this:</p>
<ul>
<li>Take the text <b>Anjali</b></li>
<li>Put it in a box</li>
<li>Label that box <b>name</b></li>
</ul>
<p>The <code>=</code> sign here does <b>not</b> mean "equals" like in maths. It means <b>"put this into that box"</b>. Programmers call it <b>assignment</b>.</p>

<h4>Worked example 1</h4>
<pre><code>name = "Anjali"
print(name)</code></pre>
<p>Step by step:</p>
<ul>
<li>Line 1: box labelled <code>name</code> now holds the text Anjali</li>
<li>Line 2: <code>print(name)</code> — no quotes! So Python does not show the word "name". It looks inside the box called name and shows what it finds.</li>
</ul>
<p>Output:</p>
<pre><code>Anjali</code></pre>
<div class="callout"><b>Very important:</b> <code>print(name)</code> shows what is inside the box. <code>print("name")</code> shows the actual word <b>name</b>. The quotes change everything.</div>

<h3>Boxes can hold different kinds of things</h3>
<pre><code>name  = "Anjali"      # text      — needs quotes
age   = 15            # whole number — no quotes
marks = 87.5          # decimal number — no quotes
passed = True         # yes or no  — no quotes, capital T</code></pre>
<p>These four kinds have names you should learn:</p>
<ul>
<li><b>string</b> — text. Always in quotes. Short for "a string of letters".</li>
<li><b>integer</b> — a whole number. 5, 100, -3</li>
<li><b>float</b> — a number with a decimal point. 87.5, 3.14</li>
<li><b>boolean</b> — only two possible values: <code>True</code> or <code>False</code>. Capital letters matter.</li>
</ul>
<p>Anything after a <code>#</code> is a <b>comment</b>. Python ignores it completely. Comments are notes for humans reading the code.</p>

<h4>Worked example 2 — changing what is in the box</h4>
<pre><code>score = 10
print(score)

score = 25
print(score)</code></pre>
<p>What happens:</p>
<ul>
<li>Box <code>score</code> gets 10. Shows 10.</li>
<li>Box <code>score</code> gets 25. The old 10 is thrown away — a box holds only one thing at a time. Shows 25.</li>
</ul>
<p>Output:</p>
<pre><code>10
25</code></pre>
<p>This is why they are called <b>variables</b>. What is inside can vary — it can change.</p>

<h4>Worked example 3 — using boxes in maths</h4>
<pre><code>maths = 80
science = 90
total = maths + science
print(total)</code></pre>
<p>Step by step:</p>
<ul>
<li>Box <code>maths</code> holds 80</li>
<li>Box <code>science</code> holds 90</li>
<li>Python looks in both boxes, adds 80 + 90 to get 170, puts 170 in a new box called <code>total</code></li>
<li>Shows what is in <code>total</code></li>
</ul>
<p>Output: <code>170</code></p>

<h4>Worked example 4 — joining text together</h4>
<p>To show text and a variable together nicely, put the letter <b>f</b> before the opening quote, and put variable names inside curly brackets <code>{ }</code>:</p>
<pre><code>name = "Anjali"
age = 15
print(f"{name} is {age} years old")</code></pre>
<p>Output:</p>
<pre><code>Anjali is 15 years old</code></pre>
<p>This is called an <b>f-string</b> (f for "format"). It is the easiest way to mix text and variables. Use it always.</p>

<h3>Rules for naming your boxes</h3>
<ul>
<li>Use lowercase letters: <code>name</code>, not <code>Name</code></li>
<li>No spaces. Use underscore instead: <code>first_name</code></li>
<li>Cannot start with a number: <code>2marks</code> is wrong, <code>marks2</code> is fine</li>
<li><b>Choose names that explain themselves.</b> <code>x</code> tells the reader nothing. <code>total_marks</code> tells them everything.</li>
</ul>
<div class="callout"><b>Why good names matter:</b> In three weeks you will read your own code and have forgotten what you meant. Good names are a message to your future self.</div>
`,
    exercises:[
      { q:"Make a box called <code>city</code> holding the text <b>Chennai</b>, then show what is inside it.",
        starter:'city = ""\nprint(city)',
        hint:'Put Chennai inside the quotes on line 1.',
        solution:'city = "Chennai"\nprint(city)',
        check:{ all:["^Chennai$"] } },

      { q:"Make a box called <code>age</code> holding the number <b>15</b>, and show it. Remember: numbers need no quotes.",
        starter:'# your code here\n',
        hint:'age = 15  then  print(age)',
        solution:'age = 15\nprint(age)',
        check:{ all:["^15$"] } },

      { q:"Two boxes: <code>hindi</code> holds 75 and <code>english</code> holds 85. Make a third box <code>total</code> holding their sum, and show it.",
        starter:'hindi = 75\nenglish = 85\ntotal = 0   # fix this line\nprint(total)',
        hint:'total = hindi + english',
        solution:'hindi = 75\nenglish = 85\ntotal = hindi + english\nprint(total)',
        check:{ all:["^160$"] } },

      { q:"Look carefully at the difference. Run this and see the two different outputs.",
        starter:'fruit = "mango"\nprint(fruit)\nprint("fruit")',
        hint:'Without quotes it opens the box. With quotes it shows the word itself.',
        solution:'fruit = "mango"\nprint(fruit)\nprint("fruit")',
        check:{ lines:["mango","fruit"] } },

      { q:"Use an f-string to show: <b>My name is Ravi and I am 14 years old</b>. The name and age must come from the boxes.",
        starter:'name = "Ravi"\nage = 14\nprint(f"")   # fill in the f-string',
        hint:'print(f"My name is {name} and I am {age} years old")',
        solution:'name = "Ravi"\nage = 14\nprint(f"My name is {name} and I am {age} years old")',
        check:{ all:["My name is Ravi and I am 14 years old"] } },

      { q:"A box called <code>score</code> starts at 50. Add 30 to it, then show the new value.",
        starter:'score = 50\n# add 30 to score here\nprint(score)',
        hint:'score = score + 30  — this means: take what is in score, add 30, put the answer back in score.',
        solution:'score = 50\nscore = score + 30\nprint(score)',
        check:{ all:["^80$"] } },

      { q:"Three subjects: 78, 92 and 85. Store each in its own box, then show the <b>average</b>. Divide the total by 3.",
        starter:'sub1 = 78\nsub2 = 92\nsub3 = 85\n# calculate and show the average\n',
        hint:'average = (sub1 + sub2 + sub3) / 3   then print it. Answer is 85.0',
        solution:'sub1 = 78\nsub2 = 92\nsub3 = 85\naverage = (sub1 + sub2 + sub3) / 3\nprint(average)',
        check:{ all:["85\\.0"] } },

      { q:"Challenge: boxes for <code>item</code> (\"notebook\"), <code>price</code> (40) and <code>quantity</code> (3). Show a sentence like: <b>3 notebook costs 120</b>",
        starter:'item = "notebook"\nprice = 40\nquantity = 3\n# calculate the total, then use an f-string\n',
        hint:'total = price * quantity, then print(f"{quantity} {item} costs {total}")',
        solution:'item = "notebook"\nprice = 40\nquantity = 3\ntotal = price * quantity\nprint(f"{quantity} {item} costs {total}")',
        check:{ all:["3 notebook costs 120"] } },
    ],
    worksheet:[
      {q:"What is a variable? Explain using the box idea.", a:"A variable is like a box with a label. You put a value inside, and whenever you use the label, you get the value that is inside."},
      {q:"In programming, what does the = sign mean? Is it the same as in maths?", a:"No. In programming it means 'put this value into that box'. It is called assignment. In maths it means both sides are equal."},
      {q:"What is the difference between print(name) and print(\"name\")?", a:"print(name) opens the box called name and shows what is inside. print(\"name\") shows the actual word 'name' because the quotes make it plain text."},
      {q:"Name the four types and give one example of each.", a:"string (text) - \"Anjali\"\ninteger (whole number) - 15\nfloat (decimal number) - 87.5\nboolean (true or false) - True"},
      {q:"Which of these variable names are wrong, and why?\na) first_name   b) 2marks   c) total marks   d) Score", a:"b) 2marks is wrong - cannot start with a number.\nc) total marks is wrong - no spaces allowed, use total_marks.\na) and d) both work, but lowercase is the normal style, so first_name is better than Score."},
      {q:"What does the # symbol do?", a:"It makes a comment. Python ignores everything after it on that line. Comments are notes for humans reading the code."},
      {q:"What will this show?\nx = 5\nx = 9\nprint(x)", a:"9. A box holds only one thing at a time. Putting 9 in throws away the 5."},
      {q:"Write code that stores your age in a box and shows the sentence: I am __ years old", a:'age = 15\nprint(f"I am {age} years old")'},
      {q:"Why is total_marks a better variable name than t?", a:"Because it explains itself. Anyone reading the code, including you in three weeks, immediately knows what it holds. t tells you nothing."},
      {q:"A shop sells pens at 12 rupees each. Write code to find the cost of 7 pens and show it.", a:'price = 12\nquantity = 7\ntotal = price * quantity\nprint(total)\n\nAnswer: 84'},
    ]
  },

  /* ---------------- LESSON 3 ---------------- */
  {
    id:"sc3", title:"Talking to the user: input", mins:25, lang:"py",
    content:`
<h3>So far your programs are boring</h3>
<p>Everything you have written does the same thing every single time. Real programs are different — they respond to the person using them.</p>
<p>To do that, the program must be able to <b>ask a question</b> and <b>receive an answer</b>.</p>

<h3>The input instruction</h3>
<pre><code>name = input("What is your name? ")</code></pre>
<p>What happens, step by step:</p>
<ul>
<li>The program shows the question on screen: <b>What is your name?</b></li>
<li>It stops and waits. Nothing else happens until the user types something and presses Enter.</li>
<li>Whatever they typed goes into the box called <code>name</code></li>
</ul>

<h4>Worked example 1</h4>
<pre><code>name = input("What is your name? ")
print(f"Hello {name}, nice to meet you!")</code></pre>
<p>If the user types <b>Priya</b>, the output is:</p>
<pre><code>What is your name? Priya
Hello Priya, nice to meet you!</code></pre>
<p>Notice the space after the question mark inside the quotes. Without it, the user's typing would touch the question mark and look cramped. Small detail, but it matters.</p>

<h3>The big trap: input always gives you text</h3>
<p>This catches every single beginner. Read it twice.</p>
<p><b>Whatever the user types, input hands it to you as text — even if they typed a number.</b></p>
<pre><code>age = input("Your age? ")
print(age + 1)</code></pre>
<p>If the user types 15, this gives an <b>error</b>. Why? Because <code>age</code> holds the <i>text</i> "15", not the <i>number</i> 15. And you cannot add 1 to a piece of text. Python does not know what "15" + 1 should mean.</p>

<h3>The fix: int() converts text into a number</h3>
<pre><code>age = int(input("Your age? "))
print(age + 1)</code></pre>
<p>Now if the user types 15, the program shows 16.</p>
<p>Read the line from the inside out:</p>
<ul>
<li><code>input("Your age? ")</code> runs first — gets the text "15"</li>
<li><code>int( ... )</code> wraps around it — turns the text "15" into the number 15</li>
<li><code>age = ...</code> puts the number 15 into the box</li>
</ul>

<h4>Worked example 2 — adding two numbers from the user</h4>
<pre><code>first = int(input("First number: "))
second = int(input("Second number: "))
total = first + second
print(f"The total is {total}")</code></pre>
<p>If the user types 20 and then 35:</p>
<pre><code>First number: 20
Second number: 35
The total is 55</code></pre>
<p>Try removing both <code>int</code> wrappers and running it. With input 20 and 35 you get <b>2035</b> — because joining two pieces of text just sticks them together. This one experiment will teach you more than any explanation.</p>

<h3>Three conversion tools</h3>
<ul>
<li><code>int()</code> — text to whole number. <code>int("15")</code> gives 15</li>
<li><code>float()</code> — text to decimal number. <code>float("87.5")</code> gives 87.5</li>
<li><code>str()</code> — number to text. <code>str(15)</code> gives "15"</li>
</ul>
<p>Use <code>int()</code> for ages, counts, marks out of a whole number. Use <code>float()</code> for anything that might have a decimal point, like a price or a percentage.</p>

<h4>Worked example 3 — a small calculator</h4>
<pre><code>print("Rectangle area calculator")
length = float(input("Length in cm: "))
breadth = float(input("Breadth in cm: "))
area = length * breadth
print(f"The area is {area} square cm")</code></pre>
<p>With inputs 5 and 4:</p>
<pre><code>Rectangle area calculator
Length in cm: 5
Breadth in cm: 4
The area is 20.0 square cm</code></pre>
<p>You have now written a genuinely useful tool. It works for any rectangle, not just one.</p>

<div class="callout"><b>A note about the exercises here:</b> The practice box cannot type answers for you. So in these exercises we will set the value directly instead of using input, exactly as if the user had typed it. The thinking is identical.</div>
`,
    exercises:[
      { q:"Pretend the user typed <b>Meena</b>. Greet her with: <b>Hello Meena</b>",
        starter:'name = "Meena"   # this is what the user typed\nprint(f"")       # fill this in',
        hint:'print(f"Hello {name}")',
        solution:'name = "Meena"\nprint(f"Hello {name}")',
        check:{ all:["^Hello Meena$"] } },

      { q:"This is broken. <code>age</code> holds <b>text</b>, not a number, so adding 1 fails. Fix it using <code>int()</code>.",
        starter:'age = "14"          # text, as input would give\nnext_year = age + 1\nprint(next_year)',
        hint:'Wrap it: age = int("14")   — or change the line to next_year = int(age) + 1',
        solution:'age = int("14")\nnext_year = age + 1\nprint(next_year)',
        check:{ all:["^15$"] } },

      { q:"Two numbers arrived as text: \"20\" and \"35\". Convert both and show their <b>sum</b>.",
        starter:'a = "20"\nb = "35"\n# convert both to numbers, add them, show the answer\n',
        hint:'total = int(a) + int(b)  then print(total). Answer is 55, not 2035.',
        solution:'a = "20"\nb = "35"\ntotal = int(a) + int(b)\nprint(total)',
        check:{ all:["^55$"] } },

      { q:"See the trap for yourself. Run this WITHOUT converting, and look at the strange answer.",
        starter:'a = "20"\nb = "35"\nprint(a + b)',
        hint:'Joining two pieces of text just sticks them together. You get 2035.',
        solution:'a = "20"\nb = "35"\nprint(a + b)',
        check:{ all:["^2035$"] } },

      { q:"Rectangle area. Length 8, breadth 5, both arriving as text. Show the area.",
        starter:'length = "8"\nbreadth = "5"\n# convert, multiply, show\n',
        hint:'area = int(length) * int(breadth). Answer is 40.',
        solution:'length = "8"\nbreadth = "5"\narea = int(length) * int(breadth)\nprint(area)',
        check:{ all:["^40$"] } },

      { q:"A price has a decimal, so use <code>float()</code> not <code>int()</code>. Price \"49.50\", quantity \"4\". Show the total.",
        starter:'price = "49.50"\nqty = "4"\n# total = price times quantity\n',
        hint:'total = float(price) * int(qty). Answer is 198.0',
        solution:'price = "49.50"\nqty = "4"\ntotal = float(price) * int(qty)\nprint(total)',
        check:{ all:["198"] } },

      { q:"Three marks came as text: \"90\", \"85\", \"80\". Show the total and then the average on separate lines.",
        starter:'m1, m2, m3 = "90", "85", "80"\n# line 1: the total\n# line 2: the average\n',
        hint:'total = int(m1)+int(m2)+int(m3) gives 255. Then average = total/3 gives 85.0',
        solution:'m1, m2, m3 = "90", "85", "80"\ntotal = int(m1) + int(m2) + int(m3)\nprint(total)\nprint(total / 3)',
        check:{ lines:["255","85.0"] } },

      { q:"Challenge: age \"12\" as text. Show the sentence <b>In 5 years you will be 17</b>.",
        starter:'age = "12"\n# convert, add 5, use an f-string\n',
        hint:'future = int(age) + 5, then print(f"In 5 years you will be {future}")',
        solution:'age = "12"\nfuture = int(age) + 5\nprint(f"In 5 years you will be {future}")',
        check:{ all:["In 5 years you will be 17"] } },
    ],
    worksheet:[
      {q:"What does input do?", a:"It shows a question on screen, waits for the user to type something and press Enter, then gives you whatever they typed."},
      {q:"What type of thing does input ALWAYS give you, even when the user types a number?", a:"Text (a string). Never a number, even if it looks like one."},
      {q:"Why does this fail?\nage = input(\"Age? \")\nprint(age + 1)", a:"Because age holds text, not a number. You cannot add the number 1 to a piece of text. Python does not know what that should mean."},
      {q:"How do you fix the code above?", a:"Wrap the input in int():\nage = int(input(\"Age? \"))\nprint(age + 1)"},
      {q:"What do int(), float() and str() each do?", a:"int() turns text into a whole number.\nfloat() turns text into a decimal number.\nstr() turns a number into text."},
      {q:"A user types 20 and 35 into a program that forgot to convert. The answer shown is 2035. Explain why.", a:"Both values are still text. Adding two pieces of text joins them end to end instead of doing maths. So \"20\" + \"35\" becomes \"2035\"."},
      {q:"Should you use int() or float() for a price like 49.50? Why?", a:"float(), because the price has a decimal point. int() would refuse it or lose the paise."},
      {q:"Write a program that asks for a number and shows its double.", a:'num = int(input("Enter a number: "))\nprint(num * 2)'},
      {q:"Write a program that asks for length and breadth and shows the area of a rectangle.", a:'length = float(input("Length: "))\nbreadth = float(input("Breadth: "))\nprint(f"Area is {length * breadth}")'},
      {q:"Why is there a space at the end of input(\"What is your name? \")?", a:"So the user's typing does not touch the question mark. Without the space it looks cramped: 'What is your name?Priya'"},
    ]
  }

  ]
},

/* =================================================================== */
/* TRACK 2 — MAKING PROGRAMS THINK                                     */
/* =================================================================== */
{
  id:"s-think", icon:"🧠", name:"Making Programs Think", level:"Class 8-12 · Part 2",
  color:"#4d9fff", weeks:3, lang:"Python",
  desc:"Right now your programs do the same thing every time. Now you will teach them to make decisions and to repeat work — which is where programming gets genuinely powerful.",
  outcomes:[
    "Make the program choose between different actions",
    "Repeat work automatically instead of copying lines",
    "Store many values together in a list",
    "Combine all of these to solve real problems"
  ],
  lessons:[

  /* ---------------- LESSON 4 ---------------- */
  {
    id:"sc4", title:"Making decisions: if and else", mins:30, lang:"py",
    content:`
<h3>You do this every day</h3>
<p>"<b>If</b> it is raining, take an umbrella. <b>Otherwise</b>, do not."</p>
<p>You made a decision by checking a condition. Programs do exactly this.</p>

<h3>The if statement</h3>
<pre><code>marks = 75

if marks >= 40:
    print("Pass")</code></pre>
<p>Reading it: <i>if marks is 40 or more, show Pass</i>.</p>
<p>Since marks is 75, and 75 is more than 40, it shows <b>Pass</b>.</p>
<p>If marks had been 30, nothing at all would happen. The program would skip that line completely.</p>

<h3>Two things you must get exactly right</h3>
<p><b>1. The colon.</b> There is a <code>:</code> at the end of the if line. Forget it and you get an error.</p>
<p><b>2. The indentation.</b> The <code>print</code> line is pushed in by four spaces. This is not decoration — it is how Python knows which lines belong to the if.</p>
<pre><code>if marks >= 40:
    print("Pass")          &lt;-- indented, so this only runs if the condition is true
print("Program over")      &lt;-- not indented, so this ALWAYS runs</code></pre>
<div class="callout"><b>In most other languages</b> you use curly brackets { } for this. Python uses spaces instead, which makes code cleaner to read but means you must be careful. Always use exactly four spaces.</div>

<h3>Comparing things</h3>
<pre><code>a == b     is a the same as b?      (TWO equal signs!)
a != b     is a different from b?
a >  b     is a bigger than b?
a <  b     is a smaller than b?
a >= b     is a bigger than or equal to b?
a <= b     is a smaller than or equal to b?</code></pre>
<div class="callout"><b>The single most common beginner mistake:</b> using one <code>=</code> when you mean <code>==</code>.<br>
One <code>=</code> means "put this in the box".<br>
Two <code>==</code> means "are these the same?"<br>
In an if statement you almost always want two.</div>

<h4>Worked example 1 — if and else</h4>
<pre><code>marks = 35

if marks >= 40:
    print("Pass")
else:
    print("Fail")</code></pre>
<p>Step by step:</p>
<ul>
<li>Is 35 greater than or equal to 40? No.</li>
<li>So Python skips the first block and runs the <code>else</code> block instead.</li>
</ul>
<p>Output: <code>Fail</code></p>
<p><b>else</b> means "otherwise". It runs only when the if condition was false. Exactly one of the two blocks will run — never both, never neither.</p>

<h4>Worked example 2 — more than two choices with elif</h4>
<pre><code>marks = 82

if marks >= 90:
    print("Grade A")
elif marks >= 75:
    print("Grade B")
elif marks >= 60:
    print("Grade C")
else:
    print("Grade D")</code></pre>
<p><code>elif</code> is short for "else if". Python checks each condition in order from the top and stops at the <b>first one that is true</b>.</p>
<ul>
<li>Is 82 >= 90? No. Move on.</li>
<li>Is 82 >= 75? Yes! Show Grade B and stop checking entirely.</li>
</ul>
<p>Output: <code>Grade B</code></p>
<p><b>The order matters enormously.</b> If you put <code>marks >= 60</code> first, then 82 would match it and print Grade C, which is wrong. Always go from the strictest condition to the loosest.</p>

<h4>Worked example 3 — checking two things at once</h4>
<pre><code>age = 16
has_ticket = True

if age >= 12 and has_ticket:
    print("You may enter")
else:
    print("Entry not allowed")</code></pre>
<ul>
<li><code>and</code> — BOTH conditions must be true</li>
<li><code>or</code> — at least ONE must be true</li>
<li><code>not</code> — flips true to false and false to true</li>
</ul>
<p>Here age is 16 (true) and has_ticket is True, so both are satisfied.</p>
<p>Output: <code>You may enter</code></p>

<h4>Worked example 4 — an if inside an if</h4>
<pre><code>marks = 85
attendance = 60

if marks >= 40:
    if attendance >= 75:
        print("Promoted")
    else:
        print("Passed exam but attendance too low")
else:
    print("Failed")</code></pre>
<p>The inner if only gets checked when the outer one was true. Notice the inner block is indented <b>eight</b> spaces — four for being inside the outer if, four more for being inside the inner one.</p>
<p>Output: <code>Passed exam but attendance too low</code></p>
`,
    exercises:[
      { q:"If <code>marks</code> is 40 or more, show <b>Pass</b>. Marks are 65 here.",
        starter:'marks = 65\n\nif marks >= 40:\n    # your print here\n    pass',
        hint:'Replace the word pass with print("Pass"). Keep the four spaces of indentation.',
        solution:'marks = 65\nif marks >= 40:\n    print("Pass")',
        check:{ all:["^Pass$"] } },

      { q:"Now add an <code>else</code>. Marks are 25, so it should show <b>Fail</b>.",
        starter:'marks = 25\n\nif marks >= 40:\n    print("Pass")\n# add else here\n',
        hint:'else: on its own line with no indent, then the print indented under it.',
        solution:'marks = 25\nif marks >= 40:\n    print("Pass")\nelse:\n    print("Fail")',
        check:{ all:["^Fail$"] } },

      { q:"This has a bug. It uses one = instead of two. Fix it so it shows <b>Correct</b>.",
        starter:'answer = "yes"\n\nif answer = "yes":\n    print("Correct")',
        hint:'Change = to == inside the if. One equals puts something in a box; two equals compares.',
        solution:'answer = "yes"\nif answer == "yes":\n    print("Correct")',
        check:{ all:["^Correct$"] } },

      { q:"Show whether the number is <b>Even</b> or <b>Odd</b>. Use <code>% 2 == 0</code> to test for even. The number is 7.",
        starter:'number = 7\n\n# if number % 2 == 0 then Even, otherwise Odd\n',
        hint:'% gives the remainder after dividing. If dividing by 2 leaves no remainder, it is even.',
        solution:'number = 7\nif number % 2 == 0:\n    print("Even")\nelse:\n    print("Odd")',
        check:{ all:["^Odd$"] } },

      { q:"Grades with <code>elif</code>. 90+ is A, 75+ is B, 60+ is C, below that is D. Marks are 78.",
        starter:'marks = 78\n\n# if / elif / elif / else\n',
        hint:'Go from highest to lowest. 78 is not >= 90, but it is >= 75, so B.',
        solution:'marks = 78\nif marks >= 90:\n    print("A")\nelif marks >= 75:\n    print("B")\nelif marks >= 60:\n    print("C")\nelse:\n    print("D")',
        check:{ all:["^B$"] } },

      { q:"Use <code>and</code>. Show <b>Allowed</b> only if age is 12 or more AND the person has a ticket.",
        starter:'age = 14\nhas_ticket = True\n\n# your if here, with else showing Not allowed\n',
        hint:'if age >= 12 and has_ticket:',
        solution:'age = 14\nhas_ticket = True\nif age >= 12 and has_ticket:\n    print("Allowed")\nelse:\n    print("Not allowed")',
        check:{ all:["^Allowed$"] } },

      { q:"Use <code>or</code>. A student gets a prize if they top in maths OR in science. Here they topped science only.",
        starter:'top_maths = False\ntop_science = True\n\n# show Prize if either is True, otherwise No prize\n',
        hint:'if top_maths or top_science:',
        solution:'top_maths = False\ntop_science = True\nif top_maths or top_science:\n    print("Prize")\nelse:\n    print("No prize")',
        check:{ all:["^Prize$"] } },

      { q:"Challenge: find the largest of three numbers 34, 78 and 56, and show it.",
        starter:'a, b, c = 34, 78, 56\n\n# work out which is biggest and show it\n',
        hint:'if a >= b and a >= c: print(a) — then elif for b, else for c. Answer is 78.',
        solution:'a, b, c = 34, 78, 56\nif a >= b and a >= c:\n    print(a)\nelif b >= a and b >= c:\n    print(b)\nelse:\n    print(c)',
        check:{ all:["^78$"] } },
    ],
    worksheet:[
      {q:"What is the difference between = and == ?", a:"= puts a value into a box (assignment).\n== asks whether two things are the same (comparison).\nIn an if statement you almost always want =="},
      {q:"Why does Python need indentation?", a:"Indentation tells Python which lines belong inside the if. Lines pushed in by four spaces only run when the condition is true. Lines not indented always run."},
      {q:"What does elif mean and when do you use it?", a:"It is short for 'else if'. Use it when you have more than two possible outcomes. Python checks each in order and stops at the first true one."},
      {q:"What will this show? Explain why.\nmarks = 95\nif marks >= 60:\n    print(\"C\")\nelif marks >= 90:\n    print(\"A\")", a:"It shows C, which is wrong. Python checks top to bottom and stops at the first true condition. 95 >= 60 is true, so it never reaches the check for 90. The conditions are in the wrong order - always go strictest first."},
      {q:"Explain and, or and not in your own words.", a:"and - both conditions must be true\nor - at least one must be true\nnot - flips the answer around"},
      {q:"Write code that shows Adult if age is 18 or more, otherwise Minor.", a:'if age >= 18:\n    print("Adult")\nelse:\n    print("Minor")'},
      {q:"How do you check if a number is even?", a:"Use the remainder operator: if number % 2 == 0 then it is even. % gives what is left over after dividing."},
      {q:"A cinema allows entry if age is 13 or more AND you have a ticket. Write the condition.", a:"if age >= 13 and has_ticket:"},
      {q:"Write a program that takes marks and shows: 90+ Distinction, 60-89 Pass, below 60 Fail.", a:'if marks >= 90:\n    print("Distinction")\nelif marks >= 60:\n    print("Pass")\nelse:\n    print("Fail")'},
      {q:"In the code below, will 'Done' always print, or only sometimes? Why?\nif x > 10:\n    print(\"Big\")\nprint(\"Done\")", a:"Always. 'Done' is not indented, so it is not inside the if. It runs no matter what x is."},
    ]
  },

  /* ---------------- LESSON 5 ---------------- */
  {
    id:"sc5", title:"Repeating work: loops", mins:30, lang:"py",
    content:`
<h3>The problem loops solve</h3>
<p>Suppose you want to show the numbers 1 to 5. You could write:</p>
<pre><code>print(1)
print(2)
print(3)
print(4)
print(5)</code></pre>
<p>Tedious, but fine. Now show 1 to 1000. You are not going to type a thousand lines.</p>
<p>This is what loops are for. A loop lets you write the instruction <b>once</b> and tell the computer how many times to do it.</p>

<h3>The for loop</h3>
<pre><code>for i in range(5):
    print(i)</code></pre>
<p>Output:</p>
<pre><code>0
1
2
3
4</code></pre>
<p>Reading it piece by piece:</p>
<ul>
<li><code>for</code> — start a loop</li>
<li><code>i</code> — a box that holds the current number. It changes each time round.</li>
<li><code>range(5)</code> — gives five numbers, <b>starting from 0</b>: 0, 1, 2, 3, 4</li>
<li><code>:</code> and indentation — same rules as if</li>
</ul>
<div class="callout"><b>Why does it start at 0 and not 1?</b> This confuses everybody at first. Computers have counted from 0 since the very beginning, for reasons to do with how memory addresses work. <code>range(5)</code> gives you five numbers, but they are 0 to 4, not 1 to 5. You will get used to it faster than you expect.</div>

<h3>Getting the numbers you actually want</h3>
<pre><code>range(5)         gives  0, 1, 2, 3, 4
range(1, 6)      gives  1, 2, 3, 4, 5      (starts at 1, stops BEFORE 6)
range(1, 11)     gives  1 to 10
range(0, 10, 2)  gives  0, 2, 4, 6, 8      (the 2 means: count in steps of 2)</code></pre>
<p>With two numbers, the first is where to start and the second is where to stop — and it always stops <i>before</i> the second number, never on it.</p>

<h4>Worked example 1 — the 7 times table</h4>
<pre><code>for i in range(1, 11):
    print(f"7 x {i} = {7 * i}")</code></pre>
<p>Output:</p>
<pre><code>7 x 1 = 7
7 x 2 = 14
7 x 3 = 21
... and so on to ...
7 x 10 = 70</code></pre>
<p>Two lines of code did the work of ten. That is the point of loops.</p>

<h4>Worked example 2 — adding up numbers</h4>
<pre><code>total = 0

for i in range(1, 6):
    total = total + i

print(total)</code></pre>
<p>Let us trace it carefully, round by round:</p>
<pre><code>Start:        total = 0
Round 1: i=1  total = 0 + 1 = 1
Round 2: i=2  total = 1 + 2 = 3
Round 3: i=3  total = 3 + 3 = 6
Round 4: i=4  total = 6 + 4 = 10
Round 5: i=5  total = 10 + 5 = 15
Loop ends
print shows 15</code></pre>
<p>Notice <code>print</code> is <b>not</b> indented. It sits outside the loop, so it runs once at the end. If you indented it, you would see the running total five times instead.</p>
<p><b>Tracing code like this — writing down what each variable holds after each round — is the single most useful debugging skill you can learn.</b> When a loop misbehaves, trace it on paper.</p>

<h4>Worked example 3 — looping over words</h4>
<p>Loops are not only for numbers:</p>
<pre><code>for fruit in ["mango", "apple", "banana"]:
    print(f"I like {fruit}")</code></pre>
<p>Output:</p>
<pre><code>I like mango
I like apple
I like banana</code></pre>
<p>The box <code>fruit</code> holds a different item each time round.</p>

<h3>The while loop</h3>
<p>A <code>for</code> loop runs a known number of times. A <code>while</code> loop keeps going <b>until something changes</b>.</p>
<pre><code>count = 1

while count <= 3:
    print(count)
    count = count + 1

print("Finished")</code></pre>
<p>Output:</p>
<pre><code>1
2
3
Finished</code></pre>
<p>Before each round, Python checks: is count still 3 or less? When count reaches 4, the answer is no, and the loop stops.</p>

<div class="callout"><b>Danger — the infinite loop.</b> If you forget the line <code>count = count + 1</code>, count stays at 1 forever, the condition is always true, and the program never stops. Your screen fills with 1s until you force it to quit. Every programmer has done this. Always check: does something inside the loop change the condition?</div>

<h4>Worked example 4 — a loop inside a loop</h4>
<pre><code>for i in range(1, 4):
    for j in range(1, 4):
        print(f"{i} x {j} = {i * j}")</code></pre>
<p>The outer loop runs 3 times. For <b>each</b> of those, the inner loop runs 3 times. So you get 3 x 3 = 9 lines in total.</p>
<p>Think of it like a clock: the outer loop is the hour hand, the inner loop is the minute hand. The minutes complete a full cycle for every single hour.</p>
`,
    exercises:[
      { q:"Show the numbers <b>0 to 4</b>, one per line.",
        starter:'for i in range(5):\n    # show i here\n    pass',
        hint:'Replace pass with print(i)',
        solution:'for i in range(5):\n    print(i)',
        check:{ lines:["0","1","2","3","4"] } },

      { q:"Now show <b>1 to 5</b> instead. You will need two numbers in range.",
        starter:'for i in range(5):    # fix this\n    print(i)',
        hint:'range(1, 6) — it starts at 1 and stops before 6.',
        solution:'for i in range(1, 6):\n    print(i)',
        check:{ lines:["1","2","3","4","5"] } },

      { q:"Show the <b>3 times table</b> from 3 x 1 to 3 x 5, in the form <b>3 x 1 = 3</b>",
        starter:'for i in range(1, 6):\n    # use an f-string\n    pass',
        hint:'print(f"3 x {i} = {3 * i}")',
        solution:'for i in range(1, 6):\n    print(f"3 x {i} = {3 * i}")',
        check:{ lines:["3 x 1 = 3","3 x 2 = 6","3 x 3 = 9","3 x 4 = 12","3 x 5 = 15"] } },

      { q:"Add up all numbers from <b>1 to 10</b> and show only the final total.",
        starter:'total = 0\nfor i in range(1, 11):\n    # add i to total\n    pass\nprint(total)',
        hint:'total = total + i inside the loop. The answer is 55.',
        solution:'total = 0\nfor i in range(1, 11):\n    total = total + i\nprint(total)',
        check:{ all:["^55$"] } },

      { q:"Show only the <b>even</b> numbers from 2 to 10. Use the third number in range.",
        starter:'# range(start, stop, step)\n',
        hint:'range(2, 11, 2) counts 2, 4, 6, 8, 10',
        solution:'for i in range(2, 11, 2):\n    print(i)',
        check:{ lines:["2","4","6","8","10"] } },

      { q:"Loop over this list and greet each person as <b>Hello Asha</b> and so on.",
        starter:'names = ["Asha", "Ravi", "Meena"]\nfor name in names:\n    # your print here\n    pass',
        hint:'print(f"Hello {name}")',
        solution:'names = ["Asha", "Ravi", "Meena"]\nfor name in names:\n    print(f"Hello {name}")',
        check:{ lines:["Hello Asha","Hello Ravi","Hello Meena"] } },

      { q:"Use a <code>while</code> loop to count down from 3 to 1, then show <b>Go</b>.",
        starter:'count = 3\nwhile count >= 1:\n    print(count)\n    # what is missing here?\nprint("Go")',
        hint:'count = count - 1 — without it the loop never ends.',
        solution:'count = 3\nwhile count >= 1:\n    print(count)\n    count = count - 1\nprint("Go")',
        check:{ lines:["3","2","1","Go"] } },

      { q:"Challenge: count how many numbers between 1 and 20 divide exactly by 3, and show the count.",
        starter:'count = 0\nfor i in range(1, 21):\n    # if i divides by 3 with no remainder, add 1 to count\n    pass\nprint(count)',
        hint:'if i % 3 == 0: count = count + 1. The numbers are 3,6,9,12,15,18 so the answer is 6.',
        solution:'count = 0\nfor i in range(1, 21):\n    if i % 3 == 0:\n        count = count + 1\nprint(count)',
        check:{ all:["^6$"] } },
    ],
    worksheet:[
      {q:"Why do we use loops instead of writing the same line many times?", a:"So we can write an instruction once and tell the computer how many times to repeat it. Writing 1000 lines by hand is impossible; a loop does it in two lines."},
      {q:"What numbers does range(5) give?", a:"0, 1, 2, 3, 4 - five numbers, but starting from 0, not 1."},
      {q:"What numbers does range(1, 6) give?", a:"1, 2, 3, 4, 5 - it starts at the first number and stops BEFORE the second."},
      {q:"What does the third number in range(0, 10, 2) do?", a:"It is the step - how much to count by. This gives 0, 2, 4, 6, 8."},
      {q:"What is the difference between a for loop and a while loop?", a:"A for loop runs a known number of times. A while loop keeps going until a condition stops being true."},
      {q:"What is an infinite loop and how do you accidentally create one?", a:"A loop that never stops. It happens when nothing inside the loop changes the condition - for example forgetting count = count + 1 in a while loop."},
      {q:"Trace this code. Write down total after each round.\ntotal = 0\nfor i in range(1, 4):\n    total = total + i\nprint(total)", a:"Start: total = 0\nRound 1: i=1, total = 1\nRound 2: i=2, total = 3\nRound 3: i=3, total = 6\nOutput: 6"},
      {q:"Write a loop that shows the 5 times table from 5x1 to 5x10.", a:'for i in range(1, 11):\n    print(f"5 x {i} = {5 * i}")'},
      {q:"What is the difference between putting print inside the loop versus outside it?", a:"Inside (indented) it runs every round. Outside (not indented) it runs once, after the loop has completely finished."},
      {q:"How many lines will this print in total? Explain.\nfor i in range(1, 4):\n    for j in range(1, 4):\n        print(i, j)", a:"9 lines. The outer loop runs 3 times, and for each of those the inner loop runs 3 times. 3 x 3 = 9."},
    ]
  },

  /* ---------------- LESSON 6 ---------------- */
  {
    id:"sc6", title:"Many things in one box: lists", mins:30, lang:"py",
    content:`
<h3>The problem</h3>
<p>You want to store the marks of 5 students. So far you would write:</p>
<pre><code>mark1 = 78
mark2 = 92
mark3 = 65
mark4 = 88
mark5 = 71</code></pre>
<p>Now do it for 50 students. Or 500. This does not work.</p>

<h3>A list is a box with many compartments</h3>
<pre><code>marks = [78, 92, 65, 88, 71]</code></pre>
<p>One box called <code>marks</code>, holding five values in order. Square brackets <code>[ ]</code> around them, commas between them.</p>

<h3>Getting one item out</h3>
<p>Each item has a position number, called its <b>index</b>. <b>Counting starts at 0.</b></p>
<pre><code>marks = [78, 92, 65, 88, 71]
          0   1   2   3   4      &lt;-- these are the index numbers

print(marks[0])    shows 78    (the first item)
print(marks[2])    shows 65    (the third item)
print(marks[-1])   shows 71    (the LAST item, counting backwards)</code></pre>
<div class="callout"><b>The most common list error:</b> A list with 5 items has indexes 0, 1, 2, 3 and 4. There is no index 5. Asking for <code>marks[5]</code> gives an "index out of range" error. The last index is always one less than the number of items.</div>

<h3>Useful things you can do</h3>
<pre><code>marks = [78, 92, 65, 88, 71]

len(marks)          how many items?     gives 5
sum(marks)          add them all up     gives 394
max(marks)          the biggest         gives 92
min(marks)          the smallest        gives 65
sum(marks)/len(marks)   the average     gives 78.8</code></pre>
<p>These four built-in tools do a lot of the work for you.</p>

<h4>Worked example 1 — the class average</h4>
<pre><code>marks = [78, 92, 65, 88, 71]

total = sum(marks)
count = len(marks)
average = total / count

print(f"Total: {total}")
print(f"Average: {average}")</code></pre>
<p>Output:</p>
<pre><code>Total: 394
Average: 78.8</code></pre>

<h3>Changing a list</h3>
<pre><code>fruits = ["mango", "apple"]

fruits.append("banana")     add to the end
fruits[0] = "papaya"        replace the first item
fruits.remove("apple")      remove that item
fruits.sort()               put in order
print(fruits)</code></pre>
<p><code>append</code> is the one you will use most. It adds a new item to the end of the list.</p>

<h4>Worked example 2 — building a list with a loop</h4>
<pre><code>squares = []                    start with an empty list

for i in range(1, 6):
    squares.append(i * i)       add each square to the list

print(squares)</code></pre>
<p>Tracing it:</p>
<pre><code>Start:        squares = []
Round 1: i=1  squares = [1]
Round 2: i=2  squares = [1, 4]
Round 3: i=3  squares = [1, 4, 9]
Round 4: i=4  squares = [1, 4, 9, 16]
Round 5: i=5  squares = [1, 4, 9, 16, 25]</code></pre>
<p>Output: <code>[1, 4, 9, 16, 25]</code></p>
<p>This pattern — start empty, loop, append — is one you will use constantly.</p>

<h4>Worked example 3 — looping through a list</h4>
<pre><code>marks = [78, 92, 65, 88, 71]

for m in marks:
    if m >= 75:
        print(f"{m} - Good")
    else:
        print(f"{m} - Needs work")</code></pre>
<p>Output:</p>
<pre><code>78 - Good
92 - Good
65 - Needs work
88 - Good
71 - Needs work</code></pre>
<p>Here you have combined all three ideas: a list, a loop, and a decision. This is real programming.</p>

<h4>Worked example 4 — counting things that match</h4>
<pre><code>marks = [78, 92, 65, 88, 71]
passed = 0

for m in marks:
    if m >= 75:
        passed = passed + 1

print(f"{passed} out of {len(marks)} scored 75 or above")</code></pre>
<p>Output: <code>3 out of 5 scored 75 or above</code></p>
<p>The pattern here: set a counter to 0 before the loop, add 1 inside the loop when the condition matches, show the counter after. Learn this shape — it answers a huge number of questions.</p>
`,
    exercises:[
      { q:"Show the <b>first</b> item of this list.",
        starter:'marks = [78, 92, 65, 88, 71]\nprint(marks[ ])   # which number goes here?',
        hint:'Counting starts at 0, so the first item is marks[0]',
        solution:'marks = [78, 92, 65, 88, 71]\nprint(marks[0])',
        check:{ all:["^78$"] } },

      { q:"Show the <b>third</b> item of the list.",
        starter:'marks = [78, 92, 65, 88, 71]\n# third item\n',
        hint:'First is 0, second is 1, third is 2. So marks[2], which is 65.',
        solution:'marks = [78, 92, 65, 88, 71]\nprint(marks[2])',
        check:{ all:["^65$"] } },

      { q:"Show how many items are in the list, then the total of all of them, on two lines.",
        starter:'marks = [78, 92, 65, 88, 71]\n# line 1: how many\n# line 2: the total\n',
        hint:'len(marks) gives 5, sum(marks) gives 394',
        solution:'marks = [78, 92, 65, 88, 71]\nprint(len(marks))\nprint(sum(marks))',
        check:{ lines:["5","394"] } },

      { q:"Show the <b>highest</b> mark, then the <b>lowest</b>, then the <b>average</b>, on three lines.",
        starter:'marks = [78, 92, 65, 88, 71]\n# highest, lowest, average\n',
        hint:'max(marks), min(marks), then sum(marks)/len(marks) which gives 78.8',
        solution:'marks = [78, 92, 65, 88, 71]\nprint(max(marks))\nprint(min(marks))\nprint(sum(marks) / len(marks))',
        check:{ lines:["92","65","78.8"] } },

      { q:"Add <b>95</b> to the end of the list, then show the whole list.",
        starter:'marks = [78, 92, 65]\n# add 95 to the end\nprint(marks)',
        hint:'marks.append(95)',
        solution:'marks = [78, 92, 65]\nmarks.append(95)\nprint(marks)',
        check:{ all:["78.*92.*65.*95"] } },

      { q:"Build a list of the squares of 1 to 5 using a loop, then show it. Expected: [1, 4, 9, 16, 25]",
        starter:'squares = []\nfor i in range(1, 6):\n    # append i times i\n    pass\nprint(squares)',
        hint:'squares.append(i * i)',
        solution:'squares = []\nfor i in range(1, 6):\n    squares.append(i * i)\nprint(squares)',
        check:{ all:["1.*4.*9.*16.*25"] } },

      { q:"Loop through the marks. For each, show <b>Pass</b> if 40 or more, else <b>Fail</b>, one per line.",
        starter:'marks = [55, 30, 80, 25]\nfor m in marks:\n    # if / else here\n    pass',
        hint:'if m >= 40: print("Pass") else: print("Fail")',
        solution:'marks = [55, 30, 80, 25]\nfor m in marks:\n    if m >= 40:\n        print("Pass")\n    else:\n        print("Fail")',
        check:{ lines:["Pass","Fail","Pass","Fail"] } },

      { q:"Challenge: count how many marks are 75 or above, and show just that number.",
        starter:'marks = [78, 92, 65, 88, 71, 45, 96]\ncount = 0\n# loop, check, count\nprint(count)',
        hint:'Inside the loop: if m >= 75: count = count + 1. The answer is 4.',
        solution:'marks = [78, 92, 65, 88, 71, 45, 96]\ncount = 0\nfor m in marks:\n    if m >= 75:\n        count = count + 1\nprint(count)',
        check:{ all:["^4$"] } },
    ],
    worksheet:[
      {q:"What is a list and why is it better than making 50 separate variables?", a:"A list is one box holding many values in order. With 50 separate variables you would need 50 names and could not loop over them. A list lets you store any number and process them all with one loop."},
      {q:"In the list [10, 20, 30, 40], what is the index of the value 30?", a:"2. Counting starts at 0, so 10 is index 0, 20 is index 1, 30 is index 2."},
      {q:"A list has 6 items. What is the index of the last one?", a:"5. The last index is always one less than the number of items."},
      {q:"What does marks[-1] give you?", a:"The last item in the list. Negative indexes count backwards from the end."},
      {q:"What do len(), sum(), max() and min() do?", a:"len() - how many items\nsum() - adds them all up\nmax() - the biggest\nmin() - the smallest"},
      {q:"How would you find the average of a list called marks?", a:"sum(marks) / len(marks)"},
      {q:"What does append do?", a:"Adds a new item to the end of the list."},
      {q:"Trace this. What is in squares at the end?\nsquares = []\nfor i in range(1, 4):\n    squares.append(i * i)", a:"Round 1: i=1, squares = [1]\nRound 2: i=2, squares = [1, 4]\nRound 3: i=3, squares = [1, 4, 9]\nFinal: [1, 4, 9]"},
      {q:"Write code to count how many numbers in a list are greater than 50.", a:'count = 0\nfor n in numbers:\n    if n > 50:\n        count = count + 1\nprint(count)'},
      {q:"Why does asking for marks[5] fail when the list has exactly 5 items?", a:"Because the indexes are 0, 1, 2, 3, 4. There is no index 5. This gives an 'index out of range' error."},
    ]
  }

  ]
},

/* =================================================================== */
/* TRACK 3 — BUILD AND EXPLORE                                          */
/* =================================================================== */
{
  id:"s-build", icon:"🚀", name:"Build Things & Meet AI", level:"Class 8-12 · Part 3",
  color:"#ff9933", weeks:2, lang:"Python",
  desc:"Put everything together to build real working programs. Then find out what Artificial Intelligence actually is, without the hype.",
  outcomes:[
    "Write your own functions to organise code",
    "Build complete working programs from scratch",
    "Explain in plain words what AI really is and is not",
    "Know exactly what to learn next"
  ],
  lessons:[

  /* ---------------- LESSON 7 ---------------- */
  {
    id:"sc7", title:"Your own instructions: functions", mins:30, lang:"py",
    content:`
<h3>The problem</h3>
<p>Suppose you need to calculate the average of marks in five different places in your program. You copy the same three lines five times. Then you find a mistake in the calculation. Now you have five places to fix, and you will miss one.</p>

<h3>A function is an instruction you invent yourself</h3>
<p>You already use functions: <code>print()</code>, <code>len()</code>, <code>sum()</code>. Someone wrote those for you. Now you write your own.</p>
<pre><code>def greet():
    print("Hello!")
    print("Welcome to Python")</code></pre>
<p>Piece by piece:</p>
<ul>
<li><code>def</code> — short for "define". It means: I am creating a new instruction.</li>
<li><code>greet</code> — the name you are giving it. You choose this.</li>
<li><code>()</code> — brackets. Information goes in here (empty for now).</li>
<li><code>:</code> and indentation — same rules as always.</li>
</ul>
<p><b>Writing the function does not run it.</b> It only teaches Python what <code>greet</code> means. To actually run it, you <b>call</b> it:</p>
<pre><code>greet()</code></pre>
<p>Output:</p>
<pre><code>Hello!
Welcome to Python</code></pre>
<p>Now you can call <code>greet()</code> a hundred times and it does the same thing each time.</p>

<h3>Giving the function information</h3>
<pre><code>def greet(name):
    print(f"Hello {name}!")

greet("Asha")
greet("Ravi")</code></pre>
<p>Output:</p>
<pre><code>Hello Asha!
Hello Ravi!</code></pre>
<p>The word <code>name</code> inside the brackets is called a <b>parameter</b>. It is an empty box that gets filled with whatever you pass in when you call the function.</p>

<h4>Worked example 1 — sending back an answer</h4>
<p>Most useful functions calculate something and <b>give it back</b> to you. That is what <code>return</code> does.</p>
<pre><code>def add(a, b):
    answer = a + b
    return answer

result = add(5, 3)
print(result)</code></pre>
<p>Step by step:</p>
<ul>
<li>You call <code>add(5, 3)</code></li>
<li>Inside the function, <code>a</code> becomes 5 and <code>b</code> becomes 3</li>
<li>It works out 5 + 3 = 8</li>
<li><code>return answer</code> sends the 8 back out</li>
<li>That 8 lands in the box <code>result</code></li>
</ul>
<p>Output: <code>8</code></p>

<div class="callout"><b>print versus return — this trips up everybody.</b><br>
<code>print</code> shows something on screen. That is all it does. The value is gone afterwards.<br>
<code>return</code> hands the value back so the rest of your program can use it.<br>
A function that prints is a dead end. A function that returns can be built on.</div>

<h4>Worked example 2 — a useful function</h4>
<pre><code>def average(numbers):
    total = sum(numbers)
    count = len(numbers)
    return total / count

class_a = [78, 92, 65]
class_b = [88, 71, 95, 60]

print(average(class_a))
print(average(class_b))</code></pre>
<p>Output:</p>
<pre><code>78.33333333333333
78.5</code></pre>
<p>You wrote the calculation once. Now it works on any list you give it, forever. If you ever need to fix it, there is exactly one place to look.</p>

<h4>Worked example 3 — a function that decides</h4>
<pre><code>def grade(marks):
    if marks >= 90:
        return "A"
    elif marks >= 75:
        return "B"
    elif marks >= 60:
        return "C"
    else:
        return "D"

print(grade(95))
print(grade(80))
print(grade(45))</code></pre>
<p>Output:</p>
<pre><code>A
B
D</code></pre>
<p>Important detail: <code>return</code> immediately ends the function. The moment it hits <code>return "A"</code>, it stops and sends A back. It never checks the other conditions.</p>

<h3>What makes a good function</h3>
<ul>
<li><b>It does one thing.</b> A function called <code>average</code> should calculate an average, not also print a report and save a file.</li>
<li><b>Its name says what it does.</b> <code>calculate_total</code> is good. <code>doStuff</code> is not.</li>
<li><b>It returns rather than prints</b>, unless showing something is genuinely its whole job.</li>
</ul>
`,
    exercises:[
      { q:"Write a function called <code>greet</code> that shows <b>Hello!</b>, then call it.",
        starter:'def greet():\n    # your print here\n    pass\n\ngreet()',
        hint:'Replace pass with print("Hello!")',
        solution:'def greet():\n    print("Hello!")\n\ngreet()',
        check:{ all:["^Hello!$"] } },

      { q:"Make the function accept a name, so <code>greet(\"Asha\")</code> shows <b>Hello Asha</b>.",
        starter:'def greet(name):\n    # use an f-string\n    pass\n\ngreet("Asha")',
        hint:'print(f"Hello {name}")',
        solution:'def greet(name):\n    print(f"Hello {name}")\n\ngreet("Asha")',
        check:{ all:["^Hello Asha$"] } },

      { q:"Write <code>double</code> that <b>returns</b> a number multiplied by 2. Do not print inside it.",
        starter:'def double(n):\n    # return n times 2\n    pass\n\nprint(double(7))',
        hint:'return n * 2',
        solution:'def double(n):\n    return n * 2\n\nprint(double(7))',
        check:{ all:["^14$"] } },

      { q:"Write <code>add</code> that takes two numbers and returns their sum.",
        starter:'def add(a, b):\n    pass\n\nprint(add(25, 17))',
        hint:'return a + b',
        solution:'def add(a, b):\n    return a + b\n\nprint(add(25, 17))',
        check:{ all:["^42$"] } },

      { q:"Write <code>area</code> that returns length times breadth. Test it with 8 and 5.",
        starter:'def area(length, breadth):\n    pass\n\nprint(area(8, 5))',
        hint:'return length * breadth',
        solution:'def area(length, breadth):\n    return length * breadth\n\nprint(area(8, 5))',
        check:{ all:["^40$"] } },

      { q:"Write <code>average</code> that takes a list and returns its average. Test with [80, 90, 100].",
        starter:'def average(numbers):\n    pass\n\nprint(average([80, 90, 100]))',
        hint:'return sum(numbers) / len(numbers). The answer is 90.0',
        solution:'def average(numbers):\n    return sum(numbers) / len(numbers)\n\nprint(average([80, 90, 100]))',
        check:{ all:["90\\.0"] } },

      { q:"Write <code>grade</code> returning A for 90+, B for 75+, C for 60+, else D. Test with 95, 80 and 45.",
        starter:'def grade(marks):\n    # if / elif / else with returns\n    pass\n\nprint(grade(95))\nprint(grade(80))\nprint(grade(45))',
        hint:'Each branch has its own return. return "A" if marks >= 90, and so on.',
        solution:'def grade(marks):\n    if marks >= 90:\n        return "A"\n    elif marks >= 75:\n        return "B"\n    elif marks >= 60:\n        return "C"\n    else:\n        return "D"\n\nprint(grade(95))\nprint(grade(80))\nprint(grade(45))',
        check:{ lines:["A","B","D"] } },

      { q:"Challenge: write <code>is_even</code> that returns True or False, then use it in a loop to show only the even numbers from 1 to 10.",
        starter:'def is_even(n):\n    pass\n\nfor i in range(1, 11):\n    # if is_even(i) then print i\n    pass',
        hint:'return n % 2 == 0 gives True or False directly. Then: if is_even(i): print(i)',
        solution:'def is_even(n):\n    return n % 2 == 0\n\nfor i in range(1, 11):\n    if is_even(i):\n        print(i)',
        check:{ lines:["2","4","6","8","10"] } },
    ],
    worksheet:[
      {q:"What is a function?", a:"An instruction you write yourself, with a name. Once written, you can use it as many times as you like by calling its name."},
      {q:"What does def mean?", a:"Short for 'define'. It tells Python you are creating a new instruction."},
      {q:"Does writing a function make it run?", a:"No. Writing it only teaches Python what it means. To actually run it you must call it, like greet()"},
      {q:"What is a parameter?", a:"An empty box inside the function's brackets that gets filled with whatever value you pass in when you call it."},
      {q:"Explain the difference between print and return.", a:"print shows something on screen and then the value is gone.\nreturn hands the value back to the rest of the program so it can be stored or used further.\nA function that prints is a dead end; one that returns can be built upon."},
      {q:"What happens the moment a function hits a return statement?", a:"It stops immediately and sends that value back. Any code after it in the function never runs."},
      {q:"Write a function that returns the square of a number.", a:'def square(n):\n    return n * n'},
      {q:"Write a function that takes a list and returns the largest value, without using max().", a:'def largest(numbers):\n    biggest = numbers[0]\n    for n in numbers:\n        if n > biggest:\n            biggest = n\n    return biggest'},
      {q:"Name three things that make a function good.", a:"1. It does one thing only\n2. Its name explains what it does\n3. It returns a value rather than printing, unless printing is its whole purpose"},
      {q:"Why is a function better than copying the same three lines five times?", a:"If you find a mistake, there is only one place to fix it. With five copies you must fix all five and you will miss one."},
    ]
  },

  /* ---------------- LESSON 8 ---------------- */
  {
    id:"sc8", title:"Build real programs", mins:35, lang:"py",
    content:`
<h3>You now know enough to build things</h3>
<p>Look at what you have learned: variables, input, if/else, loops, lists, functions. That is genuinely the core of programming. Everything else is built on these six ideas.</p>
<p>This lesson is about putting them together.</p>

<h3>How to approach any programming problem</h3>
<p>Beginners open the editor and start typing. That is the slowest way. Do this instead:</p>
<ul>
<li><b>Step 1 — Write the steps in plain English first.</b> On paper. No code.</li>
<li><b>Step 2 — Work out what to store.</b> What variables do you need?</li>
<li><b>Step 3 — Write one small piece and test it.</b> Do not write the whole thing then run it.</li>
<li><b>Step 4 — Add the next piece and test again.</b></li>
</ul>
<p>Writing a hundred lines then running it for the first time means a hundred lines of possible mistakes. Writing five lines and testing means the mistake is in those five lines.</p>

<h4>Worked example 1 — a marks report</h4>
<p><b>Step 1, plain English:</b></p>
<pre><code>1. Have a list of marks
2. Work out the total
3. Work out the average
4. Find the highest and lowest
5. Count how many passed
6. Show a neat report</code></pre>
<p><b>Step 2, the code:</b></p>
<pre><code>marks = [78, 92, 65, 88, 45, 71]

total = sum(marks)
average = total / len(marks)
highest = max(marks)
lowest = min(marks)

passed = 0
for m in marks:
    if m >= 40:
        passed = passed + 1

print("--- CLASS REPORT ---")
print(f"Students:  {len(marks)}")
print(f"Total:     {total}")
print(f"Average:   {average:.1f}")
print(f"Highest:   {highest}")
print(f"Lowest:    {lowest}")
print(f"Passed:    {passed}")</code></pre>
<p>Output:</p>
<pre><code>--- CLASS REPORT ---
Students:  6
Total:     439
Average:   73.2
Highest:   92
Lowest:    45
Passed:    6</code></pre>
<p>The <code>:.1f</code> inside the curly brackets means "show this number with 1 digit after the decimal point". Without it you would see 73.16666666666667, which looks messy.</p>

<h4>Worked example 2 — a number guessing game</h4>
<pre><code>secret = 7
guesses = [3, 9, 7]        pretend these are what the user typed

for guess in guesses:
    if guess == secret:
        print(f"{guess} - Correct!")
    elif guess < secret:
        print(f"{guess} - Too low")
    else:
        print(f"{guess} - Too high")</code></pre>
<p>Output:</p>
<pre><code>3 - Too low
9 - Too high
7 - Correct!</code></pre>
<p>A real version would use <code>input()</code> inside a <code>while</code> loop that keeps going until the guess is right.</p>

<h4>Worked example 3 — a shopping bill</h4>
<pre><code>items = ["Notebook", "Pen", "Eraser"]
prices = [40, 12, 5]
quantities = [3, 5, 2]

total = 0

print("--- BILL ---")
for i in range(len(items)):
    cost = prices[i] * quantities[i]
    total = total + cost
    print(f"{items[i]} x{quantities[i]} = {cost}")

print(f"TOTAL: {total}")</code></pre>
<p>Output:</p>
<pre><code>--- BILL ---
Notebook x3 = 120
Pen x5 = 60
Eraser x2 = 10
TOTAL: 190</code></pre>
<p>The new trick here is <code>range(len(items))</code>. It gives 0, 1, 2 — the index numbers. That lets you reach into all three lists at the same position, so item 0 pairs with price 0 and quantity 0.</p>

<h3>When your program does not work</h3>
<p>It will not work the first time. That is normal, not a sign of failure. Here is how to find the problem:</p>
<ul>
<li><b>Read the error's last line.</b> It tells you the line number and what went wrong.</li>
<li><b>Add print statements everywhere.</b> Put <code>print(variable_name)</code> at different points to see what is actually inside your boxes. Usually you will find something is not what you assumed.</li>
<li><b>Trace on paper.</b> Write down each variable's value after each line. Slow, but it finds bugs nothing else will.</li>
<li><b>Check the common ones:</b> = instead of ==, forgotten colon, wrong indentation, text where a number should be.</li>
</ul>
<div class="callout"><b>Frustration is part of the process, not a sign you are bad at this.</b> Every programmer, at every level, spends a large part of their time confused about why something does not work. The difference between a beginner and an expert is not that experts avoid bugs — it is that they have seen more of them before.</div>
`,
    exercises:[
      { q:"Show the total and the average of these marks, on two lines. Round the average to 1 decimal place using <code>:.1f</code>.",
        starter:'marks = [80, 75, 90, 85]\n# line 1: total\n# line 2: average with one decimal\n',
        hint:'print(sum(marks)) then print(f"{sum(marks)/len(marks):.1f}") — total 330, average 82.5',
        solution:'marks = [80, 75, 90, 85]\nprint(sum(marks))\nprint(f"{sum(marks) / len(marks):.1f}")',
        check:{ lines:["330","82.5"] } },

      { q:"Count how many students passed (40 or more) and how many failed. Show both on two lines.",
        starter:'marks = [55, 30, 80, 25, 60]\npassed = 0\nfailed = 0\n# loop and count\nprint(passed)\nprint(failed)',
        hint:'if m >= 40: passed = passed + 1, else: failed = failed + 1. Answers: 3 and 2.',
        solution:'marks = [55, 30, 80, 25, 60]\npassed = 0\nfailed = 0\nfor m in marks:\n    if m >= 40:\n        passed = passed + 1\n    else:\n        failed = failed + 1\nprint(passed)\nprint(failed)',
        check:{ lines:["3","2"] } },

      { q:"Guessing game. The secret is 7. For each guess show <b>Too low</b>, <b>Too high</b> or <b>Correct</b>.",
        starter:'secret = 7\nguesses = [3, 9, 7]\nfor guess in guesses:\n    # if / elif / else\n    pass',
        hint:'Compare guess with secret using ==, < and else.',
        solution:'secret = 7\nguesses = [3, 9, 7]\nfor guess in guesses:\n    if guess == secret:\n        print("Correct")\n    elif guess < secret:\n        print("Too low")\n    else:\n        print("Too high")',
        check:{ lines:["Too low","Too high","Correct"] } },

      { q:"Shopping bill. Show only the final total of all items.",
        starter:'prices = [40, 12, 5]\nquantities = [3, 5, 2]\ntotal = 0\n# loop using range(len(prices))\nprint(total)',
        hint:'for i in range(len(prices)): total = total + prices[i] * quantities[i]. Answer is 190.',
        solution:'prices = [40, 12, 5]\nquantities = [3, 5, 2]\ntotal = 0\nfor i in range(len(prices)):\n    total = total + prices[i] * quantities[i]\nprint(total)',
        check:{ all:["^190$"] } },

      { q:"Show each name with its mark, like <b>Asha: 78</b>, using the index trick.",
        starter:'names = ["Asha", "Ravi", "Meena"]\nmarks = [78, 65, 92]\nfor i in range(len(names)):\n    # f-string using names[i] and marks[i]\n    pass',
        hint:'print(f"{names[i]}: {marks[i]}")',
        solution:'names = ["Asha", "Ravi", "Meena"]\nmarks = [78, 65, 92]\nfor i in range(len(names)):\n    print(f"{names[i]}: {marks[i]}")',
        check:{ lines:["Asha: 78","Ravi: 65","Meena: 92"] } },

      { q:"Find the name of the student with the <b>highest</b> mark and show it.",
        starter:'names = ["Asha", "Ravi", "Meena"]\nmarks = [78, 65, 92]\n# find the position of the highest mark, then show that name\n',
        hint:'best = 0, then loop comparing marks[i] > marks[best], then print(names[best]). Answer: Meena',
        solution:'names = ["Asha", "Ravi", "Meena"]\nmarks = [78, 65, 92]\nbest = 0\nfor i in range(len(marks)):\n    if marks[i] > marks[best]:\n        best = i\nprint(names[best])',
        check:{ all:["^Meena$"] } },

      { q:"Write a function <code>report</code> that takes a list and returns the average, then use it on two different lists.",
        starter:'def report(marks):\n    pass\n\nprint(report([80, 90]))\nprint(report([70, 60, 50]))',
        hint:'return sum(marks) / len(marks). Answers: 85.0 and 60.0',
        solution:'def report(marks):\n    return sum(marks) / len(marks)\n\nprint(report([80, 90]))\nprint(report([70, 60, 50]))',
        check:{ lines:["85.0","60.0"] } },

      { q:"Final challenge: from the marks list, show the total, the average to 1 decimal, and how many scored above the average. Three lines.",
        starter:'marks = [60, 70, 80, 90, 100]\n# total, average (1 dp), count above average\n',
        hint:'Total 400, average 80.0, and 2 students scored above 80.',
        solution:'marks = [60, 70, 80, 90, 100]\ntotal = sum(marks)\navg = total / len(marks)\ncount = 0\nfor m in marks:\n    if m > avg:\n        count = count + 1\nprint(total)\nprint(f"{avg:.1f}")\nprint(count)',
        check:{ lines:["400","80.0","2"] } },
    ],
    worksheet:[
      {q:"List the four steps for approaching a programming problem.", a:"1. Write the steps in plain English first, on paper\n2. Work out what you need to store (the variables)\n3. Write one small piece and test it\n4. Add the next piece and test again"},
      {q:"Why is it a bad idea to write 100 lines before running anything?", a:"Because if it fails you have 100 lines of possible mistakes to search through. Writing 5 lines and testing means the bug is in those 5 lines."},
      {q:"What does :.1f do inside an f-string?", a:"Shows the number with exactly 1 digit after the decimal point. It turns 73.16666666 into 73.2"},
      {q:"What does range(len(items)) give you and why is it useful?", a:"It gives the index numbers 0, 1, 2 and so on. This is useful when you have two or more lists that match up, so you can reach the same position in each."},
      {q:"Name four ways to find a bug in your program.", a:"1. Read the last line of the error message - it gives the line number\n2. Add print statements to see what is actually in your variables\n3. Trace on paper, writing each variable's value line by line\n4. Check the common mistakes: = vs ==, missing colon, wrong indentation"},
      {q:"List four mistakes beginners make most often.", a:"Using = instead of ==\nForgetting the colon at the end of if/for/def lines\nWrong indentation\nUsing text where a number is needed (forgetting int())"},
      {q:"Write a program that finds the largest number in a list without using max().", a:'biggest = numbers[0]\nfor n in numbers:\n    if n > biggest:\n        biggest = n\nprint(biggest)'},
      {q:"You have names = [\"A\",\"B\"] and marks = [50, 90]. Write code to show each name with its mark.", a:'for i in range(len(names)):\n    print(f"{names[i]}: {marks[i]}")'},
      {q:"A student says 'I keep getting errors so I should give up.' Write what you would tell them.", a:"Errors are completely normal and happen to every programmer at every level, all day, every day. An error is just the computer telling you which line it did not understand. Experts do not avoid bugs - they have simply seen more of them before. Read the error, fix that line, run again."},
      {q:"Design (in plain English only, no code) a program that manages a class attendance register.", a:"Sample answer:\n1. Have a list of student names\n2. Have a matching list to record present or absent\n3. Loop through each name and ask if they are present\n4. Store each answer in the second list\n5. Count how many are present\n6. Show the total present, total absent, and the percentage"},
    ]
  },

  /* ---------------- LESSON 9 ---------------- */
  {
    id:"sc9", title:"What Artificial Intelligence really is", mins:30, lang:"read",
    content:`
<h3>Let us clear up the confusion first</h3>
<p>You hear "AI" everywhere. Films show robots that think and feel. News says AI will take everyone's jobs. Some people say it is magic; others say it is dangerous.</p>
<p>Most of that is noise. Here is what is actually true.</p>

<h3>Normal programs versus AI</h3>
<p>In every program you have written so far, <b>you</b> wrote the rules:</p>
<pre><code>if marks >= 40:
    print("Pass")</code></pre>
<p>You decided that 40 is the pass mark. The computer just followed your instruction.</p>
<p><b>AI is different. With AI, the computer works out the rules by itself, by looking at lots of examples.</b></p>

<h3>An example that makes it clear</h3>
<p>Suppose you want a program that tells cats apart from dogs in photographs.</p>
<p><b>The normal way</b> would be to write rules: if the ears are pointed and the face is round and the whiskers are long, then it is a cat. You would fail. There are millions of cats and they all look different. Some dogs have pointed ears too. You could write rules for years and never finish.</p>
<p><b>The AI way:</b> show the computer 50,000 photos of cats and 50,000 photos of dogs, each one labelled. The computer looks for patterns by itself. Nobody tells it what to look for. After enough examples, it can look at a photo it has never seen before and say "cat" — usually correctly.</p>
<div class="callout"><b>That is the whole idea.</b> Instead of writing the rules, you show examples and let the computer find the rules. This is called <b>machine learning</b>, and it is what almost everyone means when they say "AI".</div>

<h3>How the learning actually happens</h3>
<p>You already understand loops, so you can understand this. The computer repeats four steps, millions of times:</p>
<ul>
<li><b>1. Guess.</b> At the start the guesses are random and terrible.</li>
<li><b>2. Check.</b> Compare the guess with the correct answer.</li>
<li><b>3. Measure how wrong it was.</b> This number is called the <b>loss</b>.</li>
<li><b>4. Adjust slightly</b> in the direction that would have been less wrong.</li>
</ul>
<p>Then repeat. Millions of times. Each round the guesses get very slightly better. That is all "training a model" means.</p>
<p>Think of learning to shoot a basketball. First shot misses to the left. You adjust slightly right. Next shot is closer. You keep adjusting. Nobody gives you a formula — you learn from the gap between what you did and what you wanted. A computer learns the same way, just much faster and with numbers instead of muscles.</p>

<h3>Where you already meet AI every day</h3>
<ul>
<li><b>YouTube recommendations</b> — learned from what millions of people watched next</li>
<li><b>Google Photos finding your face</b> — learned from labelled face examples</li>
<li><b>Voice typing in your language</b> — learned from thousands of hours of recorded speech</li>
<li><b>Spam filters</b> — learned from emails people marked as spam</li>
<li><b>Google Maps traffic</b> — learned from millions of phones moving along roads</li>
<li><b>ChatGPT and similar</b> — learned from an enormous amount of text</li>
</ul>

<h3>What about ChatGPT?</h3>
<p>This one is worth understanding properly, because it is so widely misunderstood.</p>
<p>A chatbot like ChatGPT does exactly one thing: <b>it predicts what word should come next.</b></p>
<p>If you type "The capital of India is", it has seen that pattern countless times in text, and the word that almost always follows is "Delhi". So it says Delhi. Then it predicts the next word after that, and the next, one at a time.</p>
<p>Do that well enough and it can write essays, answer questions and produce code.</p>
<div class="callout"><b>This is why chatbots sometimes state wrong things very confidently.</b> They are not looking up facts in a database. They are predicting what text sounds most likely. Usually the likely-sounding answer is also correct — but not always. This is called <b>hallucination</b>, and it cannot be completely fixed, only reduced. <b>Always check anything important against a real source.</b></div>

<h3>What AI genuinely cannot do</h3>
<p>Cutting through the film-hype:</p>
<ul>
<li><b>It does not understand anything.</b> It finds patterns in numbers. When a chatbot writes "I am happy to help", it does not feel happy. It has no feelings at all.</li>
<li><b>It cannot think about things it never saw.</b> It only knows patterns from its training examples.</li>
<li><b>It is not conscious and does not want anything.</b> It has no goals, no plans, no self.</li>
<li><b>It copies our mistakes.</b> If the examples it learned from were unfair, its answers will be unfair too. This is called <b>bias</b>, and it is a serious real-world problem — for example, a hiring system trained on past hiring that favoured one group will keep favouring that group.</li>
</ul>

<h3>Will AI take everyone's jobs?</h3>
<p>Here is an honest answer rather than a scary or a comforting one.</p>
<p>AI is very good at repetitive tasks with clear patterns — sorting documents, basic data entry, simple translation. Those jobs are genuinely changing.</p>
<p>AI is poor at anything needing judgement, real understanding of people, physical skill in messy environments, or responsibility for a decision that matters.</p>
<p>What has actually happened with every major technology — printing, electricity, computers — is that some jobs disappeared, many changed, and new ones appeared that nobody had imagined. Calculators did not end mathematics. But people who understood calculators did better than people who refused to learn them.</p>
<p><b>The useful position is not to fear it or worship it, but to understand how it works — which you now do better than most adults.</b></p>

<h3>Where to go next</h3>
<p>You have finished the school track. You genuinely understand programming basics and what AI is. If you want to keep going:</p>
<ul>
<li><b>Practise what you know.</b> Build small programs for real things — a marks calculator for your class, a quiz game, a shopping list app. Building beats reading.</li>
<li><b>Then move to the main tracks on this site.</b> They cover Python in depth, then databases, then machine learning properly. They are written for older students, but you now have the foundation to follow them.</li>
<li><b>Learn maths seriously.</b> Especially anything involving averages, percentages, graphs and probability. AI is built on these. Your school maths is not separate from this — it is the actual foundation.</li>
</ul>
<p>You started this track not knowing what a program was. You can now write one that makes decisions, repeats work, handles lists of data and organises itself into functions. That is a real skill and you built it in nine lessons.</p>
`,
    exercises:[
      { q:"Concept check — write your answer, then compare with the model answer.",
        starter:"In your own words, what is the main difference between a normal program and AI?\n\nYour answer:\n",
        hint:"Think about who decides the rules.",
        answer:"In a normal program, YOU write the rules. You decide that 40 is the pass mark, and the computer just follows your instruction.\n\nIn AI, the computer works out the rules ITSELF by looking at many labelled examples. Nobody tells it what to look for.\n\nThat is the whole difference: rules written by a human, versus rules discovered by the computer from examples." },

      { q:"Explain the four steps of how an AI learns.",
        starter:"How does a computer 'learn'? Write the four steps:\n\n1.\n2.\n3.\n4.\n",
        hint:"It is a loop that repeats millions of times.",
        answer:"1. GUESS - at the start the guesses are random and terrible\n2. CHECK - compare the guess with the correct answer\n3. MEASURE how wrong it was - this number is called the loss\n4. ADJUST slightly in the direction that would have been less wrong\n\nThen repeat, millions of times. Each round the guesses get slightly better.\n\nIt is like learning to shoot a basketball - you miss, you see how far off you were, you adjust, you try again." },

      { q:"Why do chatbots sometimes give confidently wrong answers?",
        starter:"A chatbot told your friend a completely false fact, but sounded very sure.\nExplain why this happens.\n\nYour answer:\n",
        hint:"What is the chatbot actually doing when it writes?",
        answer:"A chatbot predicts what word is most likely to come next. It is not looking up facts in a database.\n\nMost of the time, text that sounds likely is also true - so the answers are usually right. But sometimes a false statement sounds just as likely as a true one, and the chatbot produces it with exactly the same confidence.\n\nIt has no way of knowing the difference, because it was never checking facts in the first place.\n\nThis is called HALLUCINATION. It can be reduced but not completely removed. Always check anything important against a real source." },

      { q:"List three things AI genuinely cannot do.",
        starter:"Three things AI cannot do:\n\n1.\n2.\n3.\n",
        hint:"Think about understanding, feelings, and where its knowledge comes from.",
        answer:"1. It does not UNDERSTAND anything. It finds patterns in numbers. When it writes 'I am happy to help', it feels nothing.\n\n2. It cannot think about things it never saw. It only knows patterns from its training examples.\n\n3. It is not conscious and wants nothing. No goals, no plans, no self.\n\n4. (Bonus) It copies our mistakes. If the examples it learned from were unfair, its answers will be unfair too. This is called bias." },

      { q:"Bias - the most important real-world problem.",
        starter:"A company builds an AI to pick which job applicants to interview.\nIt learns from the company's hiring decisions over the last 20 years.\nDuring those 20 years, the company mostly hired men.\n\nWhat will the AI do, and why?\n\nYour answer:\n",
        hint:"The AI learns patterns from examples. What pattern is in this data?",
        answer:"The AI will mostly recommend men, and reject good women applicants.\n\nWhy: the AI has no idea what 'fair' means. It only finds patterns in the examples it was given. The pattern in this data is 'people who get hired here are usually men'. So it learns that pattern and repeats it.\n\nThe AI is not being deliberately unfair - it is faithfully copying the unfairness that was already in the data.\n\nThis is called BIAS and it is one of the most serious real problems with AI today. It has genuinely happened at real companies.\n\nThe lesson: an AI is only as fair as the examples it learned from. Always ask - where did this data come from, and what unfairness might already be inside it?" },

      { q:"Spot the AI in your own life.",
        starter:"Name three places you personally have used AI in the last week,\nand for each one say what examples it must have learned from.\n\n1.\n2.\n3.\n",
        hint:"Think about your phone. What predicts, recommends or recognises things?",
        answer:"Sample answers:\n\n1. YouTube recommendations - learned from what millions of people watched next after each video\n\n2. Voice typing / Google Assistant - learned from thousands of hours of recorded speech matched with the correct text\n\n3. Google Photos grouping faces - learned from huge numbers of labelled face photographs\n\n4. Spam filter in email - learned from emails that people marked as spam\n\n5. Google Maps traffic - learned from millions of phones moving along roads at different speeds\n\nThe common thread: every one of them learned from a very large number of examples, not from rules a person wrote." },

      { q:"The jobs question - think it through properly.",
        starter:"Your relative says 'Do not learn computers, AI will take all those jobs anyway.'\n\nWrite a thoughtful reply. Do not just agree or disagree.\n\nYour answer:\n",
        hint:"What is AI good at? What is it bad at? What happened with past technologies?",
        answer:"A good answer covers three things:\n\nWHAT AI IS GOOD AT: repetitive tasks with clear patterns - sorting documents, basic data entry, simple translation. Those jobs really are changing, and it would be dishonest to pretend otherwise.\n\nWHAT AI IS BAD AT: anything needing judgement, genuine understanding of people, physical skill in messy environments, or taking responsibility for a decision that matters.\n\nWHAT HISTORY SHOWS: with printing, electricity and computers, some jobs disappeared, many changed, and new ones appeared that nobody had imagined. Calculators did not end mathematics.\n\nTHE CONCLUSION: the risk is not that AI takes every job. It is being the person who never learned how it works. People who understood calculators did better than people who refused to learn them.\n\nNote: this is a genuinely debated topic and reasonable people disagree about how big the disruption will be. The honest position is that nobody knows the scale for certain." },
    ],
    worksheet:[
      {q:"What is the main difference between a normal program and AI?", a:"In a normal program the human writes the rules. In AI the computer works out the rules itself by looking at many examples."},
      {q:"Why would writing rules to tell cats from dogs in photos fail?", a:"There are millions of cats and they all look different. Some dogs share features with cats. You could write rules for years and never cover every case."},
      {q:"What is machine learning?", a:"The method where you show a computer many labelled examples and it finds the patterns itself, instead of you writing the rules."},
      {q:"Write the four steps of how an AI learns.", a:"1. Guess (randomly at first)\n2. Check against the correct answer\n3. Measure how wrong it was (the loss)\n4. Adjust slightly to be less wrong\nThen repeat millions of times."},
      {q:"What does a chatbot like ChatGPT actually do?", a:"It predicts what word should come next, over and over, one word at a time. It is not looking up facts."},
      {q:"What is hallucination and why can it not be fully fixed?", a:"When an AI states something false very confidently. It cannot be fully fixed because the AI predicts likely-sounding text rather than checking facts - it has no way to tell a true statement from a false one that sounds equally likely."},
      {q:"List four things AI cannot do.", a:"1. Understand anything - it only finds patterns in numbers\n2. Feel emotions\n3. Think about things it never saw in training\n4. Want anything - it has no goals or consciousness"},
      {q:"What is bias in AI? Give an example.", a:"When an AI copies unfairness that was already in its training examples. Example: a hiring AI trained on 20 years of decisions that mostly hired men will learn to recommend men and reject good women applicants. It is not being deliberately unfair - it is faithfully repeating the pattern it was shown."},
      {q:"Name four places you meet AI in everyday life.", a:"YouTube recommendations, voice typing, Google Photos face grouping, spam filters, Google Maps traffic, chatbots."},
      {q:"Give a balanced answer to: will AI take all the jobs?", a:"AI is good at repetitive tasks with clear patterns, and those jobs are genuinely changing. It is poor at judgement, understanding people, physical skill and responsibility.\n\nWith past technologies - printing, electricity, computers - some jobs went, many changed, and new ones appeared. Calculators did not end mathematics.\n\nHonestly, nobody knows the exact scale of the change. But understanding how AI works puts you in a far better position than ignoring it."},
      {q:"Now that you have finished this track, what are three good next steps?", a:"1. Build small real programs - a marks calculator, a quiz game, a shopping list\n2. Move on to the main tracks on this site for Python in depth, then databases, then machine learning\n3. Take school maths seriously, especially averages, percentages, graphs and probability - AI is built on these"},
    ]
  }

  ]
}

];

if (typeof module !== "undefined") module.exports = { SCHOOL };
