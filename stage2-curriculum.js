/* ==========================================================================
   VidyaPath — STAGE 2: PYTHON PROPERLY
   Continues directly from the school track. Nothing is assumed beyond it.
   Every idea taught in full. No videos required.
   Run:  node convert-stage2.js   →  stage2.json
   ========================================================================== */

const STAGE2 = [

/* =================================================================== */
{
  id:"p2-text", icon:"📝", name:"Stage 2A · Working with Text", level:"Stage 2 · after school track",
  color:"#4d9fff", weeks:2, lang:"Python", stage:2,
  desc:"You know variables, loops and lists. Now learn to handle text properly — the skill behind every form, every file, every message your programs will ever process.",
  outcomes:[
    "Cut, join, search and clean text confidently",
    "Format numbers and text for neat output",
    "Handle messy real-world text safely",
    "Know why text bugs happen and how to prevent them"
  ],
  lessons:[

  /* ---------------- 2A.1 ---------------- */
  {
    id:"t1", title:"Text is a sequence you can cut", mins:30, lang:"py",
    content:`
<h3>Where we are</h3>
<p>In the school track you used text in simple ways — storing a name, printing a message. Now we go properly into it, because <b>most real programming is text handling</b>. Names, addresses, dates, file contents, messages, web pages — all text.</p>

<h3>A string is a row of characters, each with a position</h3>
<p>Remember how lists had positions starting at 0? Text works exactly the same way.</p>
<pre><code>word = "PYTHON"
        012345    &lt;-- position of each letter

word[0]    gives  'P'
word[3]    gives  'H'
word[-1]   gives  'N'    (last one, counting backwards)</code></pre>
<p>This is the same idea as <code>marks[0]</code> from the lists lesson. Text is just a list of letters that Python treats specially.</p>

<h3>Slicing: taking a piece out</h3>
<pre><code>word = "PYTHON"

word[0:3]    gives  'PYT'      from position 0, stop BEFORE 3
word[2:5]    gives  'THO'
word[:3]     gives  'PYT'      no start given means "from the beginning"
word[3:]     gives  'HON'      no end given means "to the end"
word[:]      gives  'PYTHON'   the whole thing</code></pre>
<p><b>The rule is always the same: start is included, end is not.</b> Same as <code>range(0, 3)</code> giving 0, 1, 2. Python is consistent about this everywhere, which is why it is worth learning once properly.</p>

<h4>Worked example 1 — pulling apart a roll number</h4>
<p>School roll numbers often encode information. Say the format is <code>2026CS042</code> — year, department, student number.</p>
<pre><code>roll = "2026CS042"

year = roll[0:4]        '2026'
dept = roll[4:6]        'CS'
num  = roll[6:]         '042'

print(year)
print(dept)
print(num)</code></pre>
<p>Let us count the positions carefully to be sure:</p>
<pre><code>2 0 2 6 C S 0 4 2
0 1 2 3 4 5 6 7 8</code></pre>
<ul>
<li><code>roll[0:4]</code> takes positions 0, 1, 2, 3 — that is 2, 0, 2, 6. Correct.</li>
<li><code>roll[4:6]</code> takes positions 4 and 5 — C and S. Correct.</li>
<li><code>roll[6:]</code> takes position 6 to the end — 0, 4, 2. Correct.</li>
</ul>
<p>Output:</p>
<pre><code>2026
CS
042</code></pre>
<div class="callout"><b>Notice something important.</b> <code>num</code> holds the <i>text</i> "042", not the number 42. If you need to do maths with it, you must convert: <code>int(num)</code> gives 42. This is the same trap as the input lesson in the school track.</div>

<h3>Length and searching</h3>
<pre><code>text = "hello world"

len(text)              11     how many characters (the space counts)
"world" in text        True   is this piece present anywhere?
text.find("world")     6      at which position does it start?
text.find("xyz")       -1     not found returns -1, it does not crash
text.count("l")        3      how many times does l appear?</code></pre>

<h4>Worked example 2 — checking an email looks reasonable</h4>
<pre><code>email = "ravi@school.edu"

has_at  = "@" in email
has_dot = "." in email

if has_at and has_dot:
    print("Looks like an email")
else:
    print("Not a valid email")</code></pre>
<p>Output: <code>Looks like an email</code></p>
<p>This is not a complete check — <code>a@b.c</code> would also pass, and real email validation is genuinely complicated. But it catches the common mistakes, and knowing the limits of your own check is part of being a good programmer.</p>

<h3>Strings cannot be changed</h3>
<p>This surprises people who have got comfortable with lists.</p>
<pre><code>marks = [10, 20, 30]
marks[0] = 99          works fine, lists can be changed

word = "hello"
word[0] = "H"          ERROR - strings cannot be changed</code></pre>
<p>Instead you build a new string:</p>
<pre><code>word = "hello"
word = "H" + word[1:]     'H' joined to 'ello'
print(word)               Hello</code></pre>
<p>The old string is thrown away and the box now holds a brand new one. Programmers say strings are <b>immutable</b> — unchangeable.</p>
`,
    exercises:[
      { q:"The word is <b>PYTHON</b>. Show the <b>first</b> letter, then the <b>last</b> letter, on two lines.",
        starter:'word = "PYTHON"\n# first letter\n# last letter\n',
        hint:'word[0] gives P. word[-1] gives N.',
        solution:'word = "PYTHON"\nprint(word[0])\nprint(word[-1])',
        check:{ lines:["P","N"] } },

      { q:"From <b>PROGRAMMING</b>, show the first <b>7</b> letters using a slice.",
        starter:'word = "PROGRAMMING"\nprint(word[  :  ])   # fill in the numbers',
        hint:'word[0:7] — start at 0, stop before 7. Gives PROGRAM.',
        solution:'word = "PROGRAMMING"\nprint(word[0:7])',
        check:{ all:["^PROGRAM$"] } },

      { q:"Split the roll number <b>2026CS042</b> into year, department and number, on three lines.",
        starter:'roll = "2026CS042"\n# year  = positions 0 to 3\n# dept  = positions 4 and 5\n# num   = position 6 onwards\n',
        hint:'roll[0:4], roll[4:6], roll[6:]',
        solution:'roll = "2026CS042"\nprint(roll[0:4])\nprint(roll[4:6])\nprint(roll[6:])',
        check:{ lines:["2026","CS","042"] } },

      { q:"Show how many characters are in the sentence, then how many times the letter <b>a</b> appears.",
        starter:'text = "data analysis is important"\n# length\n# count of the letter a\n',
        hint:'len(text) gives 26, text.count("a") gives 5',
        solution:'text = "data analysis is important"\nprint(len(text))\nprint(text.count("a"))',
        check:{ lines:["26","5"] } },

      { q:"Check whether the email has both an @ and a dot. Show <b>Valid</b> or <b>Invalid</b>.",
        starter:'email = "ravi@school.edu"\n# if it has @ AND a dot then Valid, else Invalid\n',
        hint:'if "@" in email and "." in email:',
        solution:'email = "ravi@school.edu"\nif "@" in email and "." in email:\n    print("Valid")\nelse:\n    print("Invalid")',
        check:{ all:["^Valid$"] } },

      { q:"Find at which <b>position</b> the word <b>world</b> starts. Then show what <code>find</code> gives for a word that is not there.",
        starter:'text = "hello world"\n# position of world\n# position of xyz\n',
        hint:'text.find("world") gives 6. text.find("xyz") gives -1.',
        solution:'text = "hello world"\nprint(text.find("world"))\nprint(text.find("xyz"))',
        check:{ lines:["6","-1"] } },

      { q:"Strings cannot be changed in place. Build a new string so <b>hello</b> becomes <b>Hello</b>.",
        starter:'word = "hello"\n# word[0] = "H" would ERROR. Build a new string instead.\nprint(word)',
        hint:'word = "H" + word[1:]',
        solution:'word = "hello"\nword = "H" + word[1:]\nprint(word)',
        check:{ all:["^Hello$"] } },

      { q:"Challenge: reverse the word using a slice with a step of -1, and check whether it is a palindrome. Show the reversed word, then <b>Yes</b> or <b>No</b>.",
        starter:'word = "level"\n# reversed is word[::-1]\n# then compare with the original\n',
        hint:'reversed_word = word[::-1]. Then if word == reversed_word: print("Yes")',
        solution:'word = "level"\nreversed_word = word[::-1]\nprint(reversed_word)\nif word == reversed_word:\n    print("Yes")\nelse:\n    print("No")',
        check:{ lines:["level","Yes"] } },
    ],
    worksheet:[
      {q:"In the word PYTHON, what position is the letter T at?", a:"Position 2. Counting starts at 0, so P=0, Y=1, T=2."},
      {q:"What does word[0:3] give for the word PYTHON, and why?", a:"PYT. The slice takes positions 0, 1 and 2. The start is included but the end is NOT."},
      {q:"What is the difference between word[:3] and word[3:]?", a:"word[:3] means from the beginning up to (not including) position 3.\nword[3:] means from position 3 to the very end."},
      {q:"What does word[-1] give and why is it useful?", a:"The last character. Negative positions count backwards from the end. Useful because you do not need to know the length first."},
      {q:"What does find() return when the text is not present?", a:"-1. It does not crash. This lets you check whether something was found."},
      {q:"Why does word[0] = 'H' give an error?", a:"Because strings are immutable - they cannot be changed after they are made. You must build a new string instead: word = 'H' + word[1:]"},
      {q:"A roll number is 2026CS042. Write the slices to get the year, the department and the number.", a:"year = roll[0:4]\ndept = roll[4:6]\nnum  = roll[6:]"},
      {q:"After taking num = roll[6:] you get '042'. Why can you not immediately do maths with it?", a:"Because it is still text, not a number. You must convert it first with int(num), which gives 42."},
      {q:"Write code to check if a string contains the word 'error'.", a:'if "error" in text:\n    print("Found")'},
      {q:"How would you reverse a string, and how would you check if it is a palindrome?", a:'reversed_word = word[::-1]\nif word == reversed_word:\n    print("Palindrome")'},
    ]
  },

  /* ---------------- 2A.2 ---------------- */
  {
    id:"t2", title:"Cleaning and reshaping text", mins:30, lang:"py",
    content:`
<h3>Real data is messy</h3>
<p>When people type things in, they add extra spaces, use random capitals, and make small mistakes. If your program does not handle that, it breaks in ways that look mysterious.</p>
<p>Here is the classic bug. A student types their city as <code>" Chennai "</code> with spaces, and your check fails:</p>
<pre><code>city = " Chennai "
if city == "Chennai":
    print("Found")     this NEVER runs</code></pre>
<p>The two strings look identical to a human. To the computer they are different — one has spaces. This exact bug wastes hours of people's time every day, everywhere.</p>

<h3>The cleaning tools</h3>
<pre><code>text = "  Hello World  "

text.strip()      'Hello World'    removes spaces from both ends
text.lstrip()     'Hello World  '  left side only
text.rstrip()     '  Hello World'  right side only
text.lower()      '  hello world  '   everything lowercase
text.upper()      '  HELLO WORLD  '   everything uppercase
text.title()      '  Hello World  '   First Letter Of Each Word</code></pre>

<div class="callout"><b>Critical detail:</b> none of these change the original. They <b>return a new string</b>. This is because strings are immutable, which you learned last lesson.
<pre><code>text.strip()          does nothing useful - the result is thrown away
text = text.strip()   correct - you keep the result</code></pre>
Forgetting to reassign is one of the most common beginner mistakes with strings.</div>

<h4>Worked example 1 — the safe comparison pattern</h4>
<pre><code>city = "  cHeNnAi  "
answer = city.strip().lower()

if answer == "chennai":
    print("Match found")
else:
    print("No match")</code></pre>
<p>Reading <code>city.strip().lower()</code> from left to right:</p>
<ul>
<li>Start with <code>"  cHeNnAi  "</code></li>
<li><code>.strip()</code> removes the outer spaces, giving <code>"cHeNnAi"</code></li>
<li><code>.lower()</code> is then applied to that result, giving <code>"chennai"</code></li>
</ul>
<p>Output: <code>Match found</code></p>
<p>Chaining methods like this — one after another with dots — is normal Python. Each one hands its result to the next.</p>
<p><b>Make this a habit: always clean text before comparing it.</b> <code>.strip().lower()</code> should be automatic whenever you handle anything a human typed.</p>

<h3>Splitting text apart</h3>
<pre><code>sentence = "python is really useful"
words = sentence.split()
print(words)</code></pre>
<p>Output: <code>['python', 'is', 'really', 'useful']</code></p>
<p><code>split()</code> gives you a <b>list</b> — the same lists you learned in the school track. So everything you know about lists now applies to text.</p>
<pre><code>print(len(words))       4      how many words
print(words[0])         python  the first word</code></pre>

<h4>Worked example 2 — splitting on something specific</h4>
<p>Data files often separate values with commas:</p>
<pre><code>row = "Asha,15,Chennai,88"
parts = row.split(",")

print(parts)
print(parts[0])
print(int(parts[3]) + 2)</code></pre>
<p>Output:</p>
<pre><code>['Asha', '15', 'Chennai', '88']
Asha
90</code></pre>
<p>Notice again — <code>parts[3]</code> is the text <code>"88"</code>, so it needs <code>int()</code> before doing maths. Every value that comes from splitting text is text.</p>
<p>This is exactly how spreadsheet and CSV files are read. You now understand the core of it.</p>

<h3>Joining text back together</h3>
<pre><code>words = ["python", "is", "useful"]

" ".join(words)      'python is useful'      joined with spaces
"-".join(words)      'python-is-useful'      joined with dashes
"".join(words)       'pythonisuseful'        joined with nothing</code></pre>
<p>The syntax looks backwards at first. Read it as: <i>"take this separator, and use it to join that list"</i>.</p>

<h4>Worked example 3 — cleaning a messy list of names</h4>
<pre><code>raw = "  asha , RAVI ,meena  "

names = raw.split(",")
clean = []

for n in names:
    clean.append(n.strip().title())

print(clean)</code></pre>
<p>Tracing it round by round:</p>
<pre><code>After split:   ['  asha ', ' RAVI ', 'meena  ']
Round 1: '  asha '  -> strip -> 'asha'  -> title -> 'Asha'
Round 2: ' RAVI '   -> strip -> 'RAVI'  -> title -> 'Ravi'
Round 3: 'meena  '  -> strip -> 'meena' -> title -> 'Meena'</code></pre>
<p>Output: <code>['Asha', 'Ravi', 'Meena']</code></p>
<p>You have just written a genuine data-cleaning program. This is real work that real jobs pay for.</p>

<h3>Replacing parts</h3>
<pre><code>text = "I like tea"
text.replace("tea", "coffee")     'I like coffee'

phone = "98765-43210"
phone.replace("-", "")            '9876543210'</code></pre>
<p>Again — this returns a new string. Reassign it if you want to keep the change.</p>
`,
    exercises:[
      { q:"The city has extra spaces and odd capitals. Clean it and show <b>Match</b> if it equals chennai.",
        starter:'city = "  cHeNnAi  "\nanswer = city   # clean this\nif answer == "chennai":\n    print("Match")\nelse:\n    print("No match")',
        hint:'answer = city.strip().lower()',
        solution:'city = "  cHeNnAi  "\nanswer = city.strip().lower()\nif answer == "chennai":\n    print("Match")\nelse:\n    print("No match")',
        check:{ all:["^Match$"] } },

      { q:"Split the sentence into words. Show the list, then how many words there are.",
        starter:'sentence = "python is really useful"\n# split it, print the list, print the count\n',
        hint:'words = sentence.split() then print(words) and print(len(words)). Count is 4.',
        solution:'sentence = "python is really useful"\nwords = sentence.split()\nprint(words)\nprint(len(words))',
        check:{ all:["python.*is.*really.*useful"], minLines:2 } },

      { q:"Split this comma-separated row and show the <b>name</b> and the <b>marks</b> on two lines.",
        starter:'row = "Asha,15,Chennai,88"\nparts = row.split(",")\n# name is parts[0], marks is parts[3]\n',
        hint:'print(parts[0]) then print(parts[3])',
        solution:'row = "Asha,15,Chennai,88"\nparts = row.split(",")\nprint(parts[0])\nprint(parts[3])',
        check:{ lines:["Asha","88"] } },

      { q:"From the same row, add <b>5</b> to the marks and show the result. Remember it is text.",
        starter:'row = "Asha,15,Chennai,88"\nparts = row.split(",")\n# convert parts[3] and add 5\n',
        hint:'print(int(parts[3]) + 5). Answer is 93.',
        solution:'row = "Asha,15,Chennai,88"\nparts = row.split(",")\nprint(int(parts[3]) + 5)',
        check:{ all:["^93$"] } },

      { q:"Join this list of words into one sentence separated by spaces.",
        starter:'words = ["learning", "python", "is", "fun"]\n# join with spaces\n',
        hint:'print(" ".join(words))',
        solution:'words = ["learning", "python", "is", "fun"]\nprint(" ".join(words))',
        check:{ all:["^learning python is fun$"] } },

      { q:"Remove the dashes from this phone number and show it.",
        starter:'phone = "98765-43210"\n# remove the dash\n',
        hint:'print(phone.replace("-", ""))',
        solution:'phone = "98765-43210"\nprint(phone.replace("-", ""))',
        check:{ all:["^9876543210$"] } },

      { q:"Clean this messy list of names. Show each one properly capitalised with no extra spaces, one per line.",
        starter:'raw = "  asha , RAVI ,meena  "\nnames = raw.split(",")\nfor n in names:\n    # strip and title each name\n    pass',
        hint:'print(n.strip().title())',
        solution:'raw = "  asha , RAVI ,meena  "\nnames = raw.split(",")\nfor n in names:\n    print(n.strip().title())',
        check:{ lines:["Asha","Ravi","Meena"] } },

      { q:"Challenge: from these rows, show each name with a <b>Pass</b> or <b>Fail</b> based on marks, pass mark 40.",
        starter:'rows = ["Asha,88", "Ravi,35", "Meena,60"]\nfor row in rows:\n    # split, convert marks, decide\n    pass',
        hint:'parts = row.split(","), then if int(parts[1]) >= 40: print(parts[0], "Pass")',
        solution:'rows = ["Asha,88", "Ravi,35", "Meena,60"]\nfor row in rows:\n    parts = row.split(",")\n    if int(parts[1]) >= 40:\n        print(parts[0], "Pass")\n    else:\n        print(parts[0], "Fail")',
        check:{ lines:["Asha Pass","Ravi Fail","Meena Pass"] } },
    ],
    worksheet:[
      {q:"Why does this fail?\ncity = ' Chennai '\nif city == 'Chennai':", a:"Because the stored value has spaces around it. To a human they look the same, but to the computer ' Chennai ' and 'Chennai' are different strings."},
      {q:"What does .strip() do?", a:"Removes spaces (and other whitespace) from both ends of the string."},
      {q:"What is wrong with writing text.strip() on its own line?", a:"Nothing happens usefully. Strings are immutable, so .strip() returns a NEW string. If you do not store it with text = text.strip(), the result is thrown away."},
      {q:"What is the safe pattern for comparing text a human typed?", a:"Always clean it first: value.strip().lower() before comparing. This handles extra spaces and any capitalisation."},
      {q:"What does split() return?", a:"A list. 'a b c'.split() gives ['a', 'b', 'c']"},
      {q:"How do you split on commas instead of spaces?", a:"Pass the separator: row.split(',')"},
      {q:"After splitting 'Asha,15,88' you get ['Asha','15','88']. Why can you not add 10 to the last item directly?", a:"Because it is the text '88', not the number 88. Convert first: int(parts[2]) + 10"},
      {q:"How do you join a list of words into a sentence?", a:'" ".join(words) - read it as: take this separator and use it to join that list.'},
      {q:"Write code that removes all dashes from a phone number.", a:'phone = phone.replace("-", "")'},
      {q:"Write code to clean a list of messy names so each is properly capitalised with no extra spaces.", a:'clean = []\nfor n in names:\n    clean.append(n.strip().title())'},
    ]
  },

  /* ---------------- 2A.3 ---------------- */
  {
    id:"t3", title:"Formatting output that looks professional", mins:25, lang:"py",
    content:`
<h3>Why this matters more than you think</h3>
<p>Two programs can calculate exactly the same answer. One shows:</p>
<pre><code>Average: 78.33333333333333</code></pre>
<p>The other shows:</p>
<pre><code>Average: 78.3%</code></pre>
<p>The second one looks like a finished product. The first looks unfinished. Same maths, different impression — and impressions matter when someone is deciding whether your work is any good.</p>

<h3>Recap: f-strings</h3>
<p>You met these in the school track. The <code>f</code> before the quote lets you put variables inside curly brackets:</p>
<pre><code>name = "Asha"
marks = 88
print(f"{name} scored {marks}")     Asha scored 88</code></pre>

<h3>Controlling decimal places</h3>
<p>Put a colon and a format code inside the brackets:</p>
<pre><code>value = 78.33333333333333

f"{value:.0f}"     '78'        no decimal places
f"{value:.1f}"     '78.3'      one decimal place
f"{value:.2f}"     '78.33'     two decimal places</code></pre>
<p>Read <code>:.2f</code> as "format as a number with 2 digits after the point". The <code>f</code> here means "fixed point", not the f-string f. Slightly confusing, but you get used to it.</p>

<h4>Worked example 1 — a clean marks report</h4>
<pre><code>marks = [78, 92, 65, 88, 71]
average = sum(marks) / len(marks)

print(f"Students: {len(marks)}")
print(f"Total:    {sum(marks)}")
print(f"Average:  {average:.1f}")
print(f"Highest:  {max(marks)}")</code></pre>
<p>Output:</p>
<pre><code>Students: 5
Total:    394
Average:  78.8
Highest:  92</code></pre>
<p>Without <code>:.1f</code> the average would print as 78.8 here by luck, but with other numbers you would get 78.33333333333333. Always format numbers you show to people.</p>

<h3>Lining columns up</h3>
<p>Put a number after the colon to reserve a fixed width:</p>
<pre><code>f"{name:10}"     text padded to 10 characters, left aligned
f"{marks:>5}"    padded to 5, pushed RIGHT
f"{name:<10}"    padded to 10, pushed LEFT (same as default for text)
f"{title:^20}"   centred in 20 characters</code></pre>

<h4>Worked example 2 — a neat table</h4>
<pre><code>students = [("Asha", 88), ("Ravichandran", 65), ("Meena", 92)]

print(f"{'NAME':<15}{'MARKS':>6}")
print("-" * 21)

for name, marks in students:
    print(f"{name:<15}{marks:>6}")</code></pre>
<p>Output:</p>
<pre><code>NAME            MARKS
---------------------
Asha               88
Ravichandran       65
Meena              92</code></pre>
<p>Two new things here worth noticing:</p>
<ul>
<li><code>"-" * 21</code> — multiplying text repeats it. Handy for drawing lines.</li>
<li><code>for name, marks in students</code> — each item is a pair, and Python unpacks it into two variables at once. This is called <b>tuple unpacking</b>, and it saves you writing <code>student[0]</code> and <code>student[1]</code> everywhere.</li>
</ul>
<p>Numbers are pushed right (<code>&gt;</code>) because that is how humans read numeric columns — the units line up underneath each other.</p>

<h3>Percentages and thousands separators</h3>
<pre><code>rate = 0.8756
f"{rate:.1%}"        '87.6%'      turns it into a percentage automatically

big = 1234567
f"{big:,}"           '1,234,567'  adds commas</code></pre>
<p>The <code>%</code> format multiplies by 100 and adds the sign for you. Do not multiply by 100 yourself and then add <code>%</code> — you will end up doing it twice one day.</p>

<h4>Worked example 3 — a bill</h4>
<pre><code>items = [("Notebook", 3, 45.50), ("Pen", 5, 12.00)]
total = 0

print(f"{'ITEM':<12}{'QTY':>4}{'RATE':>9}{'AMOUNT':>10}")
print("=" * 35)

for name, qty, rate in items:
    amount = qty * rate
    total = total + amount
    print(f"{name:<12}{qty:>4}{rate:>9.2f}{amount:>10.2f}")

print("=" * 35)
print(f"{'TOTAL':<12}{'':>4}{'':>9}{total:>10.2f}")</code></pre>
<p>Output:</p>
<pre><code>ITEM         QTY     RATE    AMOUNT
===================================
Notebook       3    45.50     136.50
Pen            5    12.00      60.00
===================================
TOTAL                          196.50</code></pre>
<p>Notice <code>{rate:>9.2f}</code> combines both ideas — width 9, and 2 decimal places. You can stack format instructions like this.</p>
<div class="callout"><b>A habit worth forming now:</b> whenever you show a number to a human, ask yourself how many decimal places actually make sense. Money always gets 2. Percentages usually get 1. Counts get 0. Showing 78.33333333333333 tells the reader you did not think about it.</div>
`,
    exercises:[
      { q:"Show this value with exactly <b>2</b> decimal places.",
        starter:'value = 78.33333333333333\nprint(f"{value}")   # add the format code',
        hint:'print(f"{value:.2f}") gives 78.33',
        solution:'value = 78.33333333333333\nprint(f"{value:.2f}")',
        check:{ all:["^78\\.33$"] } },

      { q:"Show the average of these marks with <b>1</b> decimal place.",
        starter:'marks = [78, 92, 65, 88, 71]\n# average with one decimal\n',
        hint:'avg = sum(marks)/len(marks) then print(f"{avg:.1f}") gives 78.8',
        solution:'marks = [78, 92, 65, 88, 71]\navg = sum(marks) / len(marks)\nprint(f"{avg:.1f}")',
        check:{ all:["^78\\.8$"] } },

      { q:"Show this as a <b>percentage</b> with 1 decimal place.",
        starter:'rate = 0.8756\n# format as a percentage\n',
        hint:'print(f"{rate:.1%}") gives 87.6%',
        solution:'rate = 0.8756\nprint(f"{rate:.1%}")',
        check:{ all:["87\\.6%"] } },

      { q:"Show this large number with <b>commas</b> as thousands separators.",
        starter:'big = 1234567\n# add commas\n',
        hint:'print(f"{big:,}") gives 1,234,567',
        solution:'big = 1234567\nprint(f"{big:,}")',
        check:{ all:["1,234,567"] } },

      { q:"Draw a line of exactly <b>20</b> dashes.",
        starter:'# multiply the text\n',
        hint:'print("-" * 20)',
        solution:'print("-" * 20)',
        check:{ all:["^-{20}$"] } },

      { q:"Print each name padded to 12 characters on the left, with marks pushed right in 5 characters.",
        starter:'students = [("Asha", 88), ("Meena", 92)]\nfor name, marks in students:\n    # f"{name:<12}{marks:>5}"\n    pass',
        hint:'print(f"{name:<12}{marks:>5}")',
        solution:'students = [("Asha", 88), ("Meena", 92)]\nfor name, marks in students:\n    print(f"{name:<12}{marks:>5}")',
        check:{ all:["Asha\\s+88","Meena\\s+92"] } },

      { q:"Show the amount as money — width 10, pushed right, exactly 2 decimals.",
        starter:'amount = 136.5\n# combine width and decimals\n',
        hint:'print(f"{amount:>10.2f}") gives spaces then 136.50',
        solution:'amount = 136.5\nprint(f"{amount:>10.2f}")',
        check:{ all:["136\\.50"] } },

      { q:"Challenge: print a small bill. For each item show name, quantity and the amount (qty times rate) to 2 decimals. Then show the total.",
        starter:'items = [("Notebook", 3, 45.50), ("Pen", 5, 12.00)]\ntotal = 0\nfor name, qty, rate in items:\n    # calculate, add to total, print\n    pass\nprint(f"TOTAL {total:.2f}")',
        hint:'amount = qty * rate; total = total + amount; print(f"{name} {qty} {amount:.2f}"). Total is 196.50',
        solution:'items = [("Notebook", 3, 45.50), ("Pen", 5, 12.00)]\ntotal = 0\nfor name, qty, rate in items:\n    amount = qty * rate\n    total = total + amount\n    print(f"{name} {qty} {amount:.2f}")\nprint(f"TOTAL {total:.2f}")',
        check:{ all:["136\\.50","60\\.00","TOTAL 196\\.50"] } },
    ],
    worksheet:[
      {q:"Why does formatting output matter if the calculation is already correct?", a:"Because unformatted output like 78.33333333333333 looks unfinished. The same answer shown as 78.3% looks like a finished product. It affects whether people trust your work."},
      {q:"What does :.2f do?", a:"Formats the number with exactly 2 digits after the decimal point."},
      {q:"How many decimal places should money have? Percentages? Counts?", a:"Money: always 2. Percentages: usually 1. Counts: 0 (they are whole numbers)."},
      {q:"What does :>5 do and when would you use it?", a:"Pads to 5 characters and pushes the content right. Used for numbers in a table so the units line up underneath each other."},
      {q:"What does :<12 do?", a:"Pads to 12 characters, pushed left. Used for names and text in a table."},
      {q:"What does 'x' * 20 produce and why is it useful?", a:"Twenty x characters in a row. Multiplying text repeats it. Useful for drawing separator lines in reports."},
      {q:"What does :.1% do to the value 0.8756?", a:"Gives 87.6%. It multiplies by 100 and adds the percent sign automatically."},
      {q:"Why should you NOT multiply by 100 yourself before using the % format?", a:"Because the % format already multiplies by 100. Doing both gives 8756.0% instead of 87.6%."},
      {q:"Explain what happens in: for name, marks in students:", a:"Each item in the list is a pair. Python unpacks it into two variables at once. This is called tuple unpacking, and it avoids writing student[0] and student[1]."},
      {q:"Write an f-string that shows a price right-aligned in 10 characters with 2 decimals.", a:'f"{price:>10.2f}"'},
    ]
  }

  ]
},

/* =================================================================== */
{
  id:"p2-data", icon:"🗂️", name:"Stage 2B · Organising Data", level:"Stage 2 · after 2A",
  color:"#8b5cf6", weeks:2, lang:"Python", stage:2,
  desc:"Lists hold values in a row. But real information has labels — a student has a name AND marks AND a city. Dictionaries let you store that properly, and they are the single most useful structure in Python.",
  outcomes:[
    "Store labelled information with dictionaries",
    "Choose correctly between a list and a dictionary",
    "Handle collections of records the way real programs do",
    "Write comprehensions to transform data in one line"
  ],
  lessons:[

  /* ---------------- 2B.1 ---------------- */
  {
    id:"d1", title:"Dictionaries: values with labels", mins:35, lang:"py",
    content:`
<h3>The problem with lists</h3>
<p>Say you store a student as a list:</p>
<pre><code>student = ["Asha", 15, "Chennai", 88]</code></pre>
<p>Now, three weeks later, you read <code>student[2]</code>. What is it? You have to count positions to find out. And if someone inserts a new field at the start, every number in your program is silently wrong.</p>

<h3>A dictionary labels each value</h3>
<pre><code>student = {
    "name": "Asha",
    "age": 15,
    "city": "Chennai",
    "marks": 88
}</code></pre>
<p>Now you write <code>student["city"]</code>. It says exactly what it is. Order does not matter. Adding new fields breaks nothing.</p>
<p>The structure is <b>key: value</b> pairs, in curly brackets, separated by commas. The <b>key</b> is the label; the <b>value</b> is what it holds.</p>

<h3>Reading and writing</h3>
<pre><code>student["name"]              'Asha'
student["marks"] = 92        change an existing value
student["email"] = "a@b.c"   add a completely new one
del student["age"]           remove one</code></pre>

<h3>The safe way to read</h3>
<pre><code>student["phone"]                    CRASHES if phone is not there
student.get("phone")                gives None instead of crashing
student.get("phone", "not given")   gives your own default instead</code></pre>
<div class="callout"><b>Use <code>.get()</code> whenever a key might be missing.</b> Real data has gaps — someone did not fill in a field, a record is incomplete. Using square brackets on missing data is one of the most common causes of programs crashing in production. <code>.get()</code> with a sensible default is almost always the right choice.</div>

<h4>Worked example 1 — a student record</h4>
<pre><code>student = {"name": "Asha", "marks": 88, "city": "Chennai"}

print(student["name"])
print(student.get("phone", "not provided"))

student["marks"] = student["marks"] + 5
print(student["marks"])</code></pre>
<p>Output:</p>
<pre><code>Asha
not provided
93</code></pre>

<h3>Looping through a dictionary</h3>
<pre><code>student = {"name": "Asha", "marks": 88, "city": "Chennai"}

for key in student:
    print(key)                 just the labels

for key, value in student.items():
    print(f"{key}: {value}")   both at once</code></pre>
<p>The second form is what you want almost always. Output:</p>
<pre><code>name: Asha
marks: 88
city: Chennai</code></pre>

<h3>A list of dictionaries — the shape of real data</h3>
<p>This combination is everywhere. Every database table, every spreadsheet, every API response looks like this:</p>
<pre><code>students = [
    {"name": "Asha",  "marks": 88, "city": "Chennai"},
    {"name": "Ravi",  "marks": 65, "city": "Pune"},
    {"name": "Meena", "marks": 92, "city": "Chennai"},
]</code></pre>
<p>A list holds the records. Each record is a dictionary with labelled fields.</p>

<h4>Worked example 2 — processing records</h4>
<pre><code>for s in students:
    print(f"{s['name']:<8} {s['marks']:>3}")</code></pre>
<p>Output:</p>
<pre><code>Asha      88
Ravi      65
Meena     92</code></pre>
<p>Note the quote marks: the f-string uses double quotes on the outside, so inside the curly brackets you use single quotes — <code>s['name']</code>. Mixing them up is a common small error.</p>

<h4>Worked example 3 — answering real questions</h4>
<pre><code>total = 0
best = students[0]
chennai_count = 0

for s in students:
    total = total + s["marks"]
    if s["marks"] > best["marks"]:
        best = s
    if s["city"] == "Chennai":
        chennai_count = chennai_count + 1

print(f"Average: {total / len(students):.1f}")
print(f"Top: {best['name']} with {best['marks']}")
print(f"From Chennai: {chennai_count}")</code></pre>
<p>Output:</p>
<pre><code>Average: 81.7
Top: Meena with 92
From Chennai: 2</code></pre>
<p>Look at what you just did. You calculated an average, found a maximum, and counted matching records — in one pass through the data. That is genuinely what data analysis is. The tools get fancier later, but the thinking is exactly this.</p>

<h3>Counting things with a dictionary</h3>
<p>This pattern comes up constantly, so learn it as a shape:</p>
<pre><code>cities = ["Chennai", "Pune", "Chennai", "Delhi", "Pune", "Chennai"]
counts = {}

for city in cities:
    if city in counts:
        counts[city] = counts[city] + 1
    else:
        counts[city] = 1

print(counts)</code></pre>
<p>Output: <code>{'Chennai': 3, 'Pune': 2, 'Delhi': 1}</code></p>
<p>There is a shorter way using the default trick:</p>
<pre><code>for city in cities:
    counts[city] = counts.get(city, 0) + 1</code></pre>
<p>Read it as: <i>take the current count (or 0 if we have not seen this city before), add one, store it back</i>. One line instead of four.</p>
`,
    exercises:[
      { q:"Make a dictionary for a student with name <b>Asha</b>, age <b>15</b> and marks <b>88</b>. Show the name.",
        starter:'student = {}   # fill this in\nprint(student["name"])',
        hint:'student = {"name": "Asha", "age": 15, "marks": 88}',
        solution:'student = {"name": "Asha", "age": 15, "marks": 88}\nprint(student["name"])',
        check:{ all:["^Asha$"] } },

      { q:"Read a key that does <b>not</b> exist, safely, so it shows <b>not provided</b> instead of crashing.",
        starter:'student = {"name": "Asha", "marks": 88}\nprint(student["phone"])   # this crashes - fix it',
        hint:'Use .get() with a default: student.get("phone", "not provided")',
        solution:'student = {"name": "Asha", "marks": 88}\nprint(student.get("phone", "not provided"))',
        check:{ all:["not provided"] } },

      { q:"Add <b>5</b> to the student's marks and show the new value.",
        starter:'student = {"name": "Asha", "marks": 88}\n# add 5 to marks\nprint(student["marks"])',
        hint:'student["marks"] = student["marks"] + 5',
        solution:'student = {"name": "Asha", "marks": 88}\nstudent["marks"] = student["marks"] + 5\nprint(student["marks"])',
        check:{ all:["^93$"] } },

      { q:"Loop through the dictionary showing each label and value as <b>key: value</b>.",
        starter:'student = {"name": "Asha", "marks": 88}\nfor key, value in student.items():\n    # print them\n    pass',
        hint:'print(f"{key}: {value}")',
        solution:'student = {"name": "Asha", "marks": 88}\nfor key, value in student.items():\n    print(f"{key}: {value}")',
        check:{ lines:["name: Asha","marks: 88"] } },

      { q:"From this list of records, show each student's name and marks, one per line, as <b>Asha 88</b>.",
        starter:'students = [\n  {"name": "Asha",  "marks": 88},\n  {"name": "Ravi",  "marks": 65},\n]\nfor s in students:\n    pass',
        hint:'print(s["name"], s["marks"])',
        solution:'students = [\n  {"name": "Asha",  "marks": 88},\n  {"name": "Ravi",  "marks": 65},\n]\nfor s in students:\n    print(s["name"], s["marks"])',
        check:{ lines:["Asha 88","Ravi 65"] } },

      { q:"Find the student with the <b>highest</b> marks and show their name.",
        starter:'students = [\n  {"name": "Asha",  "marks": 88},\n  {"name": "Ravi",  "marks": 65},\n  {"name": "Meena", "marks": 92},\n]\nbest = students[0]\n# compare each against best\nprint(best["name"])',
        hint:'if s["marks"] > best["marks"]: best = s. Answer is Meena.',
        solution:'students = [\n  {"name": "Asha",  "marks": 88},\n  {"name": "Ravi",  "marks": 65},\n  {"name": "Meena", "marks": 92},\n]\nbest = students[0]\nfor s in students:\n    if s["marks"] > best["marks"]:\n        best = s\nprint(best["name"])',
        check:{ all:["^Meena$"] } },

      { q:"Count how many times each city appears. Show the resulting dictionary.",
        starter:'cities = ["Chennai", "Pune", "Chennai", "Delhi", "Pune", "Chennai"]\ncounts = {}\nfor city in cities:\n    # use counts.get(city, 0) + 1\n    pass\nprint(counts)',
        hint:'counts[city] = counts.get(city, 0) + 1',
        solution:'cities = ["Chennai", "Pune", "Chennai", "Delhi", "Pune", "Chennai"]\ncounts = {}\nfor city in cities:\n    counts[city] = counts.get(city, 0) + 1\nprint(counts)',
        check:{ all:["Chennai.*3","Pune.*2","Delhi.*1"] } },

      { q:"Challenge: show the average marks, and count how many students are from Chennai. Two lines, average to 1 decimal.",
        starter:'students = [\n  {"name": "Asha",  "marks": 88, "city": "Chennai"},\n  {"name": "Ravi",  "marks": 65, "city": "Pune"},\n  {"name": "Meena", "marks": 92, "city": "Chennai"},\n]\n# average to 1 dp, then the Chennai count\n',
        hint:'Loop once, building total and count. Average is 81.7, Chennai count is 2.',
        solution:'students = [\n  {"name": "Asha",  "marks": 88, "city": "Chennai"},\n  {"name": "Ravi",  "marks": 65, "city": "Pune"},\n  {"name": "Meena", "marks": 92, "city": "Chennai"},\n]\ntotal = 0\nchennai = 0\nfor s in students:\n    total = total + s["marks"]\n    if s["city"] == "Chennai":\n        chennai = chennai + 1\nprint(f"{total / len(students):.1f}")\nprint(chennai)',
        check:{ lines:["81.7","2"] } },
    ],
    worksheet:[
      {q:"What is the problem with storing a student as a list like ['Asha', 15, 'Chennai', 88]?", a:"You have to remember what each position means. student[2] tells you nothing. And if someone inserts a field at the start, every position number in your program becomes silently wrong."},
      {q:"How does a dictionary solve that?", a:"Each value gets a label (a key). student['city'] says exactly what it is. Order does not matter and adding fields breaks nothing."},
      {q:"What is the difference between student['phone'] and student.get('phone')?", a:"Square brackets CRASH if the key is missing. .get() returns None instead. You can also give a default: .get('phone', 'not given')"},
      {q:"When should you use .get() instead of square brackets?", a:"Whenever the key might be missing. Real data has gaps. Using square brackets on missing data is a very common cause of crashes in real programs."},
      {q:"How do you loop through both keys and values at once?", a:"for key, value in mydict.items():"},
      {q:"Write the structure for a list of student records.", a:'students = [\n    {"name": "Asha", "marks": 88},\n    {"name": "Ravi", "marks": 65},\n]'},
      {q:"Why is 'a list of dictionaries' such an important shape?", a:"Because it is how real data looks everywhere - database tables, spreadsheets, API responses. A list holds the records; each record is a dictionary with labelled fields."},
      {q:"Write the counting pattern using .get()", a:'counts = {}\nfor item in items:\n    counts[item] = counts.get(item, 0) + 1'},
      {q:"Explain what counts.get(city, 0) + 1 does.", a:"Takes the current count for that city, or 0 if we have never seen it before, adds one, and stores it back. It replaces a four-line if/else with one line."},
      {q:"Write code to find the record with the highest marks in a list of student dictionaries.", a:'best = students[0]\nfor s in students:\n    if s["marks"] > best["marks"]:\n        best = s\nprint(best["name"])'},
    ]
  },

  /* ---------------- 2B.2 ---------------- */
  {
    id:"d2", title:"Comprehensions: transforming data in one line", mins:30, lang:"py",
    content:`
<h3>A pattern you have written many times</h3>
<p>Look at these three loops from earlier lessons:</p>
<pre><code>squares = []
for i in range(1, 6):
    squares.append(i * i)

names = []
for s in students:
    names.append(s["name"])

passed = []
for m in marks:
    if m >= 40:
        passed.append(m)</code></pre>
<p>They all have the same shape: <b>make an empty list, loop, append</b>. Python gives you a shortcut for exactly this shape.</p>

<h3>The list comprehension</h3>
<pre><code>squares = [i * i for i in range(1, 6)]
print(squares)</code></pre>
<p>Output: <code>[1, 4, 9, 16, 25]</code></p>
<p>Read it in this order:</p>
<ul>
<li>Start at the <b>middle</b>: <code>for i in range(1, 6)</code> — this is the loop, same as always</li>
<li>Then look <b>left</b>: <code>i * i</code> — this is what goes into the list each time</li>
<li>The square brackets around it mean the result is a list</li>
</ul>
<p>It is the same loop, written on one line, with the append implied.</p>

<h4>Worked example 1 — side by side</h4>
<pre><code>Long way:                      Short way:

names = []                     names = [s["name"] for s in students]
for s in students:
    names.append(s["name"])</code></pre>
<p>Both give exactly the same result. The short way is not clever showing-off — it is the normal way Python programmers write this, and you will see it constantly in real code.</p>

<h3>Adding a condition</h3>
<pre><code>marks = [78, 35, 92, 40, 65]

passed = [m for m in marks if m >= 40]
print(passed)</code></pre>
<p>Output: <code>[78, 92, 40, 65]</code></p>
<p>The <code>if</code> goes at the end and filters — only items where the condition is true get included.</p>
<p>Now read the whole thing: <i>take m, for each m in marks, if m is 40 or more</i>. It reads almost like English.</p>

<h4>Worked example 2 — transform and filter together</h4>
<pre><code>students = [
    {"name": "asha",  "marks": 88},
    {"name": "ravi",  "marks": 35},
    {"name": "meena", "marks": 92},
]

toppers = [s["name"].title() for s in students if s["marks"] >= 80]
print(toppers)</code></pre>
<p>Output: <code>['Asha', 'Meena']</code></p>
<p>Breaking it down:</p>
<ul>
<li><code>for s in students</code> — go through each record</li>
<li><code>if s["marks"] >= 80</code> — keep only the high scorers</li>
<li><code>s["name"].title()</code> — for those kept, take the name and capitalise it</li>
</ul>
<p>Ravi is skipped because 35 is below 80. The two who remain get their names tidied.</p>

<h3>When NOT to use a comprehension</h3>
<p>This is important, because beginners discover comprehensions and then cram everything into them.</p>
<pre><code>result = [x*2 if x > 0 else x*3 for y in data for x in y if x != 0]</code></pre>
<p>That is technically valid Python and completely unreadable. Nobody, including you next month, will understand it.</p>
<div class="callout"><b>The rule:</b> if the comprehension does not fit comfortably on one line, or if you have to read it twice, write the ordinary loop instead. Clear code that anyone can follow beats clever code every single time. Experienced programmers write more ordinary loops than beginners expect.</div>

<h3>Dictionary comprehensions</h3>
<p>The same idea builds dictionaries. Use curly brackets and a <code>key: value</code> pair:</p>
<pre><code>students = [
    {"name": "Asha",  "marks": 88},
    {"name": "Ravi",  "marks": 65},
]

lookup = {s["name"]: s["marks"] for s in students}
print(lookup)</code></pre>
<p>Output: <code>{'Asha': 88, 'Ravi': 65}</code></p>
<p>Why is this useful? Because now looking up any student's marks is instant:</p>
<pre><code>print(lookup["Asha"])      88</code></pre>
<p>Without it you would loop through the whole list every time you wanted one student. With 10 students that does not matter. With 10 million it matters enormously — and understanding that difference is what the Big-O lesson later is about.</p>

<h4>Worked example 3 — a small data pipeline</h4>
<pre><code>raw = ["  asha , 88 ", " ravi , 35", "meena,92 "]

records = []
for line in raw:
    parts = line.split(",")
    records.append({
        "name": parts[0].strip().title(),
        "marks": int(parts[1].strip())
    })

toppers = [r["name"] for r in records if r["marks"] >= 80]

print(records)
print(toppers)</code></pre>
<p>Output:</p>
<pre><code>[{'name': 'Asha', 'marks': 88}, {'name': 'Ravi', 'marks': 35}, {'name': 'Meena', 'marks': 92}]
['Asha', 'Meena']</code></pre>
<p>Look at what this does: takes messy text, cleans it, converts types, builds structured records, then filters them. That is a <b>data pipeline</b>, and it is the single most common thing a working data analyst writes. You have all the pieces now.</p>
`,
    exercises:[
      { q:"Rewrite this loop as a comprehension. It should give [1, 4, 9, 16, 25].",
        starter:'# squares = []\n# for i in range(1, 6):\n#     squares.append(i * i)\n\nsquares = []   # make this a comprehension\nprint(squares)',
        hint:'squares = [i * i for i in range(1, 6)]',
        solution:'squares = [i * i for i in range(1, 6)]\nprint(squares)',
        check:{ all:["1.*4.*9.*16.*25"] } },

      { q:"Use a comprehension to get a list of just the <b>names</b> from these records.",
        starter:'students = [{"name": "Asha"}, {"name": "Ravi"}]\nnames = []   # comprehension here\nprint(names)',
        hint:'names = [s["name"] for s in students]',
        solution:'students = [{"name": "Asha"}, {"name": "Ravi"}]\nnames = [s["name"] for s in students]\nprint(names)',
        check:{ all:["Asha.*Ravi"] } },

      { q:"Use a comprehension with a condition to keep only marks of <b>40 or above</b>.",
        starter:'marks = [78, 35, 92, 40, 65]\npassed = []   # add the if condition\nprint(passed)',
        hint:'passed = [m for m in marks if m >= 40]',
        solution:'marks = [78, 35, 92, 40, 65]\npassed = [m for m in marks if m >= 40]\nprint(passed)',
        check:{ all:["78.*92.*40.*65"], none:["35"] } },

      { q:"Double every number in the list using a comprehension.",
        starter:'nums = [1, 2, 3, 4]\ndoubled = []\nprint(doubled)',
        hint:'doubled = [n * 2 for n in nums]',
        solution:'nums = [1, 2, 3, 4]\ndoubled = [n * 2 for n in nums]\nprint(doubled)',
        check:{ all:["2.*4.*6.*8"] } },

      { q:"Combine both: get the names of students scoring <b>80 or more</b>, properly capitalised.",
        starter:'students = [\n  {"name": "asha",  "marks": 88},\n  {"name": "ravi",  "marks": 35},\n  {"name": "meena", "marks": 92},\n]\ntoppers = []\nprint(toppers)',
        hint:'toppers = [s["name"].title() for s in students if s["marks"] >= 80]',
        solution:'students = [\n  {"name": "asha",  "marks": 88},\n  {"name": "ravi",  "marks": 35},\n  {"name": "meena", "marks": 92},\n]\ntoppers = [s["name"].title() for s in students if s["marks"] >= 80]\nprint(toppers)',
        check:{ all:["Asha.*Meena"], none:["[Rr]avi"] } },

      { q:"Build a lookup dictionary from name to marks using a dictionary comprehension.",
        starter:'students = [\n  {"name": "Asha", "marks": 88},\n  {"name": "Ravi", "marks": 65},\n]\nlookup = {}   # dictionary comprehension\nprint(lookup["Asha"])',
        hint:'lookup = {s["name"]: s["marks"] for s in students}',
        solution:'students = [\n  {"name": "Asha", "marks": 88},\n  {"name": "Ravi", "marks": 65},\n]\nlookup = {s["name"]: s["marks"] for s in students}\nprint(lookup["Asha"])',
        check:{ all:["^88$"] } },

      { q:"Clean this messy text into a list of names, stripped and capitalised.",
        starter:'raw = ["  asha ", " RAVI", "meena  "]\nclean = []   # use a comprehension\nprint(clean)',
        hint:'clean = [n.strip().title() for n in raw]',
        solution:'raw = ["  asha ", " RAVI", "meena  "]\nclean = [n.strip().title() for n in raw]\nprint(clean)',
        check:{ all:["Asha.*Ravi.*Meena"] } },

      { q:"Challenge: build a full pipeline. Turn the messy rows into records, then show the names of those scoring 80+.",
        starter:'raw = ["  asha , 88 ", " ravi , 35", "meena,92 "]\nrecords = []\nfor line in raw:\n    parts = line.split(",")\n    # build a dict with cleaned name and int marks\n    pass\n\ntoppers = []   # comprehension filtering on marks\nprint(toppers)',
        hint:'records.append({"name": parts[0].strip().title(), "marks": int(parts[1].strip())}) then filter.',
        solution:'raw = ["  asha , 88 ", " ravi , 35", "meena,92 "]\nrecords = []\nfor line in raw:\n    parts = line.split(",")\n    records.append({"name": parts[0].strip().title(), "marks": int(parts[1].strip())})\n\ntoppers = [r["name"] for r in records if r["marks"] >= 80]\nprint(toppers)',
        check:{ all:["Asha.*Meena"], none:["Ravi"] } },
    ],
    worksheet:[
      {q:"What repeated pattern does a list comprehension replace?", a:"Make an empty list, loop over something, append to the list. That three-line shape becomes one line."},
      {q:"In what order should you read [i * i for i in range(1, 6)]?", a:"Middle first (the for loop), then left (what goes in the list each time). The brackets mean the result is a list."},
      {q:"Rewrite this as a comprehension:\nresult = []\nfor n in nums:\n    result.append(n * 3)", a:"result = [n * 3 for n in nums]"},
      {q:"How do you filter inside a comprehension?", a:"Put an if at the end: [m for m in marks if m >= 40]"},
      {q:"Write a comprehension that gets names of students with marks above 75.", a:'[s["name"] for s in students if s["marks"] > 75]'},
      {q:"When should you NOT use a comprehension?", a:"When it does not fit comfortably on one line, or when you have to read it twice to understand it. Then write the ordinary loop instead - clear beats clever."},
      {q:"What does a dictionary comprehension look like?", a:'{s["name"]: s["marks"] for s in students}\nCurly brackets, and a key: value pair before the for.'},
      {q:"Why is building a lookup dictionary useful?", a:"Because looking up one item becomes instant, instead of looping through the whole list every time. With 10 records it does not matter; with 10 million it matters enormously."},
      {q:"What is a data pipeline?", a:"Taking messy raw input, cleaning it, converting types, building structured records, then filtering or summarising. It is the most common thing a working data analyst writes."},
      {q:"Write a pipeline that turns ['a,10', 'b,20'] into a list of dictionaries with name and value.", a:'records = []\nfor line in raw:\n    parts = line.split(",")\n    records.append({"name": parts[0], "value": int(parts[1])})'},
    ]
  }

  ]
}

];

if (typeof module !== "undefined") module.exports = { STAGE2 };
