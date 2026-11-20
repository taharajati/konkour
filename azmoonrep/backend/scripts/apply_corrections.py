"""Corrections to the grade-9 sets/real-numbers bank found by re-reading every question
against its scan (2026-11-17). Run from backend/:
    python -m scripts.apply_corrections          # dry run: prints what would change
    python -m scripts.apply_corrections --write  # applies to the database in .env

Each entry replaces the transcription of a question (stem, options, key, solution) with the
version read from the scan and re-checked by hand. Only text-only questions whose answer I
derived by arithmetic or definition are set to approved; anything that depends on a figure,
or whose scan I could not read fully, goes to "pending" with a note for the manager.
The history of each question records who changed what.
"""
import json
import os
import sys
from app import clock, db

BY = "bank-audit-2026-11-17"
FA = "۰۱۲۳۴۵۶۷۸۹"


def ans(n, body):
    return f"{body}\n\n**پاسخ درست: گزینهٔ {n}**"


# status: "approved" | "pending". note: shown to the manager (pending only).
C = {
 "g9_sets_001": dict(status="approved", answer=4,
   stem="کدام عبارت یک مجموعه را مشخص می‌کند؟ (نمونه دولتی کرمان – خراسان رضوی ۹۶–۹۵)",
   options=["چهار عدد فرد متوالی", "پنج عدد بزرگ‌تر از ۱۰۰", "سه شهر ایران", "عددهای طبیعی بین ۳ و ۴"],
   solution=ans(4, "مجموعه باید اعضای دقیق و بدون ابهام داشته باشد. «چهار عدد فرد متوالی»، «پنج عدد بزرگ‌تر از ۱۰۰» و «سه شهر ایران» را می‌شود به چند شکل انتخاب کرد، پس اعضایشان مشخص نیست. «عددهای طبیعی بین ۳ و ۴» دقیقاً مشخص است: هیچ عددی ندارد و مجموعهٔ تهی است.")),
 "g9_sets_002": dict(status="approved", answer=2,
   stem="کدام یک از عبارت‌های زیر نمایش یک مجموعه است؟",
   options=["گروهی از ورزشکاران استان تهران", "عددهای اول زوج", "دو عدد زوج کمتر از ۲۲", "پنج تن از نویسندگان ایران"],
   solution=ans(2, "عضوهای «ورزشکاران استان تهران»، «دو عدد زوج کمتر از ۲۲» و «پنج تن از نویسندگان» مشخص نیستند (کدام ورزشکار؟ کدام دو عدد؟). تنها عدد اول زوج ۲ است، پس «عددهای اول زوج» یعنی $\\{2\\}$ و دقیقاً مشخص است.")),
 "g9_sets_003": dict(status="pending", answer=1,
   stem="کدام یک از عبارت‌های زیر مجموعه‌ای را مشخص نمی‌کند؟",
   options=["شش عدد فرد متوالی", "هفت عدد طبیعی متوالی با شروع از ۱۱", "شمارنده‌های ۲۵", "عددهای طبیعی بین ۴ و ۵"],
   solution=ans(1, "«شش عدد فرد متوالی» را می‌شود از هر عدد فردی شروع کرد، پس اعضایش مشخص نیست. «هفت عدد طبیعی متوالی از ۱۱» یعنی ۱۱ تا ۱۷، شمارنده‌های ۲۵ یعنی $\\{1,5,25\\}$ و «عددهای طبیعی بین ۴ و ۵» مجموعهٔ تهی است؛ هر سه مشخص‌اند."),
   note="متن گزینه‌ها از اسکن بازنویسی شد و پاسخ را خودم استنتاج کردم؛ با اسکن مقایسه و تأیید کنید."),
 "g9_sets_005": dict(status="approved", answer=3,
   stem="عدد ۳ عضو کدام یک از مجموعه‌های زیر **نیست**؟",
   options=["مجموعهٔ مقسوم‌علیه‌های اول عدد ۶", "مجموعهٔ سه عدد فرد متوالی با شروع از عدد یک", "مضارب عدد ۹", "مضارب طبیعی عدد ۳"],
   solution=ans(3, "مقسوم‌علیه‌های اول ۶ برابر $\\{2,3\\}$ است. سه عدد فرد متوالی از یک: $\\{1,3,5\\}$. مضارب ۹ عبارت‌اند از ۹، ۱۸، ... و ۳ بینشان نیست. مضارب طبیعی ۳ شامل خود ۳ است.")),
 "g9_sets_006": dict(status="pending", answer=2,
   stem="با توجه به نمودار زیر کدام یک از گزینه‌های زیر صحیح است؟",
   options=["$A-B=\\{4\\}$", "$B-A=\\{5,6,7\\}$", "$A-B=\\{5,6,7\\}$", "$B-A=\\{4\\}$"],
   solution=ans(2, "$B-A$ عضوهایی از $B$ است که در $A$ نیستند. در نمودار، ۴ اشتراک دو مجموعه است و ۵ و ۶ و ۷ فقط در $B$ هستند؛ پس $B-A=\\{5,6,7\\}$."),
   note="گزینه‌ها از اسکن بازنویسی شد؛ شکل را با اسکن مقایسه کنید."),
 "g9_sets_007": dict(status="approved", answer=3,
   stem="کدام یک از عبارت‌های زیر مجموعهٔ تهی را نشان می‌دهد؟",
   options=["عددهای طبیعی اول مضرب ۷", "عددهای صحیح بین ۱۲ و ۱۴", "عددهای اول زوج دورقمی", "عددهای طبیعی در بازهٔ $[0,1]$"],
   solution=ans(3, "عددهای اول مضرب ۷ فقط ۷ است ($\\{7\\}$). بین ۱۲ و ۱۴ عدد صحیح ۱۳ هست. در $[0,1]$ عدد طبیعی ۱ هست. تنها عدد اول زوج ۲ است که دورقمی نیست، پس مجموعهٔ سوم تهی است.")),
 "g9_sets_009": dict(status="approved", answer=4,
   stem="کدام عبارت و عدد زیر، به‌ترتیب مجموعهٔ $A=\\{7,14,21,\\ldots,91,98\\}$ و تعداد اعضای آن را بیان می‌کند؟",
   options=["۱۵ – عددهای طبیعی فرد کمتر از ۹۹", "۱۴ – عددهای طبیعی مضرب ۷", "۱۵ – مضرب‌های صحیح عدد ۷ کمتر از ۱۰۰", "۱۴ – مضرب‌های طبیعی عدد ۷ کوچک‌تر از ۱۰۰"],
   solution=ans(4, "$A=\\{1\\times7,2\\times7,\\ldots,14\\times7\\}$ و ۱۴ عضو دارد. «مضرب‌های طبیعی ۷» بدون کران نامتناهی است و «مضرب‌های صحیح» شامل صفر و منفی‌ها هم می‌شود؛ فقط «مضرب‌های طبیعی ۷ کوچک‌تر از ۱۰۰» دقیقاً همین ۱۴ عدد است.")),
 "g9_sets_010": dict(status="pending", answer=2,
   stem="نمودار ون مربوط به عبارت «جواب‌های معادلهٔ $6x+18=-6$» کدام است؟",
   options=["$\\{6,18,-6\\}$", "$\\{-4\\}$", "$\\{4\\}$", "این عبارت مجموعه نیست و نمی‌توان آن را با نمودار ون نمایش داد."],
   solution=ans(2, "$6x+18=-6\\Rightarrow 6x=-24\\Rightarrow x=-4$؛ پس مجموعهٔ جواب $\\{-4\\}$ است."),
   note="گزینه‌ها شکل‌دارند؛ شکل‌ها را با اسکن مقایسه کنید."),
 "g9_sets_011": dict(status="approved", answer=3,
   stem="کدام یک از مجموعه‌های زیر تهی است؟ (نمونه دولتی قم ۹۶–۹۵)",
   options=["عددهای طبیعی کوچک‌تر از ۸ که مکعب کامل باشند", "عددهای صحیح غیرمثبتی که مربعشان با خودشان برابر باشد", "عددهای طبیعی که مربعشان کوچک‌تر از خودشان باشد", "عددهای اول بین ۱۹ و ۲۹"],
   solution=ans(3, "مکعب‌های کامل کمتر از ۸: $\\{1\\}$. عدد غیرمثبت با $x^2=x$: $\\{0\\}$. عدد اول بین ۱۹ و ۲۹: $\\{23\\}$. برای عدد طبیعی $n$ همیشه $n^2\\ge n$ است، پس مجموعهٔ سوم تهی است.")),
 "g9_sets_012": dict(status="approved", answer=2,
   stem="کدام عبارت زیر نشان‌دهندهٔ مجموعه‌ای یک‌عضوی است؟",
   options=["عددهای طبیعی بین $-3$ و $-1$", "عددهای طبیعی که نه اول‌اند و نه مرکب", "عددهای اول یک‌رقمی", "مضرب‌های صحیح ۵"],
   solution=ans(2, "بین $-3$ و $-1$ عدد طبیعی نیست (تهی). عدد طبیعی که نه اول است نه مرکب فقط ۱ است. اول‌های یک‌رقمی چهارتایند ($2,3,5,7$) و مضرب‌های صحیح ۵ نامتناهی‌اند.")),
 "g9_sets_013": dict(status="approved", answer=3,
   stem="مجموعهٔ $A=\\{\\{\\},\\emptyset\\}$ دارای چند عضو است؟",
   options=["۲ عضو", "هیچ عضوی ندارد", "۱ عضو", "هیچ‌کدام"],
   solution=ans(3, "$\\{\\}$ و $\\emptyset$ هر دو مجموعهٔ تهی‌اند، یعنی یک عضو تکراری؛ پس $A=\\{\\emptyset\\}$ و فقط ۱ عضو دارد.")),
 "g9_sets_014": dict(status="approved", answer=1,
   stem="با توجه به مجموعهٔ $A=\\{2,\\{1\\},0,11\\}$ کدام عبارت نادرست است؟",
   options=["$1\\in A$", "$11\\in A$", "$0\\in A$", "$2\\in A$"],
   solution=ans(1, "عضوهای $A$ عبارت‌اند از $2$ و $\\{1\\}$ و $0$ و $11$. خود عدد ۱ عضو نیست (عضو، مجموعهٔ $\\{1\\}$ است)، پس $1\\in A$ نادرست است.")),
 "g9_sets_017": dict(status="pending", answer=3,
   stem="دو مجموعهٔ $A=\\{4,5,6\\}$ و $B=\\{1,2,3,4,5\\}$ را در نظر بگیرید. کدام نمودار ون نمایش دو مجموعهٔ $A$ و $B$ است؟",
   options=["نمودار ۱", "نمودار ۲", "نمودار ۳", "نمودار ۴"],
   solution=ans(3, "اشتراک دو مجموعه $\\{4,5\\}$ است، فقط ۶ در $A$ و فقط ۱ و ۲ و ۳ در $B$ هستند. نمودار درست دو دایرهٔ متقاطع با همین چینش و برچسب درست $A$ و $B$ است."),
   note="صورت سؤال اصلاح شد ($A=\\{4,5,6\\}$)؛ گزینه‌های شکلی را با اسکن مقایسه کنید."),
 "g9_sets_019": dict(status="pending", answer=2,
   stem="با توجه به نمودار، چه تعداد از عبارت‌های زیر درست است؟\n\nالف) $(A\\cap C)=A$\n\nب) $(B\\cup C)\\subseteq A$\n\nج) $(A\\cap B)=B$",
   options=["۱", "۲", "۳", "۴"],
   solution=ans(2, "در نمودار $B$ و $C$ هر دو داخل $A$ هستند. $A\\cap C=C\\neq A$ (چون ۲ فقط در $A$ است)، پس الف نادرست است. $B\\cup C\\subseteq A$ و $A\\cap B=B$ درست‌اند؛ پس ۲ عبارت درست است."),
   note="عبارت‌ها از اسکن بازنویسی شد؛ نمودار را با اسکن مقایسه کنید."),
 "g9_sets_020": dict(status="approved", answer=1,
   stem="مجموعه‌های $A=\\{x\\mid x\\in\\mathbb{N},\\;x\\le3\\}$ و $B=\\{x\\mid x\\in\\mathbb{Z},\\;-1\\le x<4\\}$ را در نظر بگیرید. کدام عبارت صحیح است؟",
   options=["$A\\cap B=\\{1,2,3\\}$", "$A\\cup B=\\{-1,0,1,2,3,4\\}$", "$B\\subseteq A$", "$B=\\{-1,0,1,2,3,4\\}$"],
   solution=ans(1, "$A=\\{1,2,3\\}$ و $B=\\{-1,0,1,2,3\\}$ (چون $x<4$، عدد ۴ در $B$ نیست). پس $A\\cap B=\\{1,2,3\\}$؛ $A\\cup B$ و $B$ هر دو ۴ را اشتباهاً دارند و $B\\not\\subseteq A$.")),
 "g9_sets_024": dict(status="approved", answer=3,
   stem="مجموعه‌های $A$ و $B$ به‌ترتیب ۵ عضو و ۷ عضو دارند و $A\\cap B=\\{2,4,6\\}$. مجموعهٔ $A\\cup B$ چند عضو دارد؟ (نمونه دولتی گلستان ۹۶–۹۵)",
   options=["۷", "۸", "۹", "۱۰"],
   solution=ans(3, "$n(A\\cup B)=n(A)+n(B)-n(A\\cap B)=5+7-3=9$.")),
 "g9_sets_026": dict(status="approved", answer=4,
   stem="در یک کلاس ۴۰ نفره، هر دانش‌آموز دست‌کم یکی از زبان‌های فرانسه یا انگلیسی را می‌داند. تعداد دانش‌آموزانی که انگلیسی می‌دانند، ۲ برابر تعداد کسانی است که فرانسه می‌دانند و ۴ برابر تعداد کسانی است که هر دو زبان را می‌دانند. چند نفر انگلیسی می‌دانند؟ (نمونه دولتی آذربایجان غربی و اردبیل ۹۶–۹۵)",
   options=["۲۰", "۲۴", "۳۰", "۳۲"],
   solution=ans(4, "اگر $x$ نفر هر دو زبان را بدانند، انگلیسی‌دان‌ها $4x$ و فرانسه‌دان‌ها $2x$ نفرند. $n(A\\cup B)=4x+2x-x=5x=40$ پس $x=8$ و انگلیسی‌دان‌ها $4\\times8=32$ نفرند.")),
 "g9_sets_027": dict(status="approved", answer=4,
   stem="مجموعهٔ $(A\\cap B)\\cup(B-A)$ با کدام مجموعه برابر است؟ (نمونه دولتی کردستان – لرستان – همدان ۹۶–۹۵)",
   options=["$A\\cup B$", "$\\emptyset$", "$A$", "$B$"],
   solution=ans(4, "$A\\cap B$ بخشی از $B$ است که در $A$ هم هست و $B-A$ بخشی از $B$ که در $A$ نیست. این دو بخش با هم همهٔ $B$ را می‌سازند.")),
 "g9_sets_028": dict(status="approved", answer=3,
   stem="احتمال اینکه در مسیر بازگشت از مدرسه به خانه باران ببارد $\\frac13$ است و احتمال اینکه سوزان چتر خود را همراه بیاورد $\\frac35$ است. اگر این دو اتفاق مستقل از هم باشند، احتمال اینکه سوزان هنگام رسیدن به خانه خیس شده باشد چقدر است؟ (مسابقات ریاضی انگلستان)",
   options=["$\\frac15$", "$\\frac25$", "$\\frac{2}{15}$", "$\\frac{11}{15}$"],
   solution=ans(3, "خیس می‌شود اگر ببارد و چتر نداشته باشد: $\\frac13\\times\\left(1-\\frac35\\right)=\\frac13\\times\\frac25=\\frac{2}{15}$.")),
 "g9_sets_031": dict(status="approved", answer=4,
   stem="مجموعه‌های $A=\\{x\\mid x^2\\in\\mathbb{N},\\;x\\le4\\}$ و $B=\\{x^2\\mid x\\in\\mathbb{N},\\;x\\le4\\}$ مفروض‌اند. مجموعهٔ $A\\cap B$ چند زیرمجموعه دارد؟ (نمونه دولتی آذربایجان غربی و اردبیل ۹۶–۹۵)",
   options=["۱", "۲", "۳", "۴"],
   solution=ans(4, "$B=\\{1,4,9,16\\}$. از اعضای $B$ فقط ۱ و ۴ در $A$ هستند ($x\\le4$ و $x^2$ طبیعی)، پس $A\\cap B=\\{1,4\\}$ دو عضو دارد و $2^2=4$ زیرمجموعه.")),
 "g9_sets_032": dict(status="approved", answer=3,
   stem="مجموعهٔ دلخواه $B$ همواره با کدام یک از مجموعه‌های زیر برابر است؟",
   options=["$(A-B)\\cup A$", "$(A-B)\\cup(A\\cap B)$", "$(B-A)\\cup(A\\cap B)$", "$A\\cap B$"],
   solution=ans(3, "$B-A$ بخشی از $B$ بیرون $A$ و $A\\cap B$ بخشی از $B$ داخل $A$ است؛ اجتماعشان همهٔ $B$ است. گزینهٔ ۲ برابر $A$ است.")),
 "g9_sets_033": dict(status="approved", answer=2,
   stem="$(A\\cap B)\\cap(A\\cap B')$ برابر کدام است؟",
   options=["$A\\cap B$", "$\\emptyset$", "$A$", "$B$"],
   solution=ans(2, "$B\\cap B'=\\emptyset$؛ پس کل عبارت تهی است.")),
 "g9_sets_034": dict(status="approved", answer=4, concept_id="G9_RIAZI_ch1_l3_k4",
   stem="اگر $A$ مجموعهٔ عددهای بخش‌پذیر بر ۳ و $B$ مجموعهٔ عددهای بخش‌پذیر بر ۵ باشد و $x\\in(A'\\cup B)'$، کدام حکم درست است؟",
   options=["$x$ بر ۳ و ۵ بخش‌پذیر است.", "$x$ بر ۵ بخش‌پذیر است و بر ۳ بخش‌پذیر نیست.", "$x$ نه بر ۳ و نه بر ۵ بخش‌پذیر است.", "$x$ بر ۳ بخش‌پذیر است و بر ۵ بخش‌پذیر نیست."],
   solution=ans(4, "طبق قانون دمورگان $(A'\\cup B)'=A\\cap B'$؛ یعنی $x$ در $A$ هست و در $B$ نیست: بر ۳ بخش‌پذیر است و بر ۵ نه.")),
 "g9_sets_035": dict(status="approved", answer=2,
   stem="فرض کنید $A_i$ مجموعهٔ مقسوم‌علیه‌های عدد $i$ باشد؛ مثلاً $A_6=\\{1,2,3,6\\}$. مجموعهٔ $A_{51}\\cup A_{52}\\cup\\cdots\\cup A_{100}$ چند عضو دارد؟",
   options=["۵۰ عضو", "۱۰۰ عضو", "۲۰۰ عضو", "۳۷۷۵ عضو"],
   solution=ans(2, "هر مقسوم‌علیه یک عدد از ۵۱ تا ۱۰۰ حداکثر ۱۰۰ است. هر $n\\le100$ عضو اجتماع است: اگر $n\\ge51$ مقسوم‌علیه خودش است و اگر $n\\le50$ مقسوم‌علیه $2n$ (که بین ۵۱ تا ۱۰۰ است) یا ضریبی مناسب از خودش است. پس اجتماع همهٔ عددهای ۱ تا ۱۰۰ است: ۱۰۰ عضو.")),
 "g9_sets_036": dict(status="approved", answer=2,
   stem="چند تا از عبارت‌های زیر صحیح است؟\n\nالف) $\\mathbb{Z}\\subseteq\\mathbb{Q}'$\n\nب) $\\mathbb{Q}\\cap\\mathbb{Q}'=\\emptyset$\n\nپ) $\\mathbb{Z}\\subseteq\\mathbb{Q}$\n\nت) $\\mathbb{N}\\subseteq\\mathbb{Z}\\subseteq\\mathbb{Q}\\subseteq\\mathbb{Q}'$",
   options=["یکی", "دو تا", "سه تا", "هیچ‌کدام"],
   solution=ans(2, "الف نادرست است (صحیح‌ها گویا هستند). ب درست است (گویا و گنگ مشترک ندارند). پ درست است. ت نادرست است ($\\mathbb{Q}\\not\\subseteq\\mathbb{Q}'$). پس ۲ عبارت درست است.")),
 "g9_sets_037": dict(status="approved", answer=4,
   stem="چند تا از جمله‌های زیر درست است؟ (نمونه دولتی یزد ۹۶–۹۵)\n\n۱) هر عدد اعشاری نامختوم یک عدد گنگ است.\n\n۲) عددی وجود دارد که صحیح باشد ولی گویا نباشد.\n\n۳) حاصل جمع دو عدد گنگ همواره یک عدد گنگ است.\n\n۴) مساحت مستطیلی به ابعاد $\\sqrt{x}$ و $\\sqrt{y}$ همواره عددی گنگ است.",
   options=["سه تا", "دو تا", "یکی", "هیچ‌کدام"],
   solution=ans(4, "۱) اعشار نامختوم متناوب گویاست. ۲) هر صحیح گویاست. ۳) $\\sqrt2+(-\\sqrt2)=0$. ۴) $\\sqrt{x}\\times\\sqrt{y}$ برای $x=y=2$ برابر ۲ است. هیچ‌کدام درست نیست.")),
 "g9_sets_038": dict(status="approved", answer=4,
   stem="اگر $D=\\{x\\in\\mathbb{R}\\mid -3\\le x<9\\}$ باشد، کدام گزینه درست است؟ (نمونه دولتی اصفهان، کهگیلویه و بویراحمد ۹۶–۹۵)",
   options=["عددی که هم گویا و هم گنگ باشد در $D$ قرار دارد.", "عدد $-3+\\sqrt[3]{-27}$ به مجموعهٔ $D$ تعلق دارد.", "مجموعهٔ $D$ با مجموعهٔ $\\{x\\in\\mathbb{Z}\\mid -3\\le x<9\\}$ مساوی است.", "$\\left(\\sqrt{19}+\\frac{11}{3}\\right)\\in D$"],
   solution=ans(4, "عددی هم گویا هم گنگ وجود ندارد. $-3+\\sqrt[3]{-27}=-6<-3$ در $D$ نیست. $D$ شامل عددهای غیرصحیح هم هست. $\\sqrt{19}\\approx4.36$ پس $\\sqrt{19}+\\frac{11}{3}\\approx8.03$ و این عدد بین $-3$ و ۹ است.")),
 "g9_sets_039": dict(status="approved", answer=4,
   stem="کدام یک از عددهای زیر گویا است؟ (نمونه دولتی بوشهر و خوزستان ۹۶–۹۵)",
   options=["$\\frac{\\pi}{3}$", "$(\\sqrt3-1)^2$", "$0.01001000100001\\ldots$", "$\\frac{3+3\\sqrt2}{2\\sqrt2+2}$"],
   solution=ans(4, "$\\frac{\\pi}{3}$ گنگ است. $(\\sqrt3-1)^2=4-2\\sqrt3$ گنگ است. اعشار گزینهٔ ۳ نه متناهی است نه متناوب. در گزینهٔ ۴: $\\frac{3(1+\\sqrt2)}{2(\\sqrt2+1)}=\\frac32$ که گویاست.")),
 "g9_sets_040": dict(status="approved", answer=1,
   stem="کدام یک از کسرهای زیر بین دو کسر $-\\frac57$ و $-\\frac67$ قرار **ندارد**؟ (تیزهوشان و نمونه دولتی بوشهر ۹۳–۹۲)",
   options=["$-\\frac{19}{21}$", "$-\\frac{17}{21}$", "$-\\frac{16}{21}$", "$-\\frac{11}{14}$"],
   solution=ans(1, "$-\\frac57=-\\frac{15}{21}$ و $-\\frac67=-\\frac{18}{21}$. عددهای بین آن‌ها از $-\\frac{18}{21}$ بزرگ‌ترند و از $-\\frac{15}{21}$ کوچک‌ترند. $-\\frac{19}{21}$ کوچک‌تر از $-\\frac{18}{21}$ است و بیرون بازه می‌افتد؛ $-\\frac{11}{14}=-\\frac{16.5}{21}$ داخل بازه است.")),
 "g9_sets_042": dict(status="approved", answer=4,
   stem="چند تا از جمله‌های زیر همواره صحیح است؟ (تیزهوشان و نمونه دولتی چهارمحال و بختیاری ۹۳–۹۲)\n\n۱) مجموع هر دو عدد گنگ، عددی گنگ است.\n\n۲) هر عدد حقیقی، عددی گویا است.\n\n۳) حاصل‌ضرب هر دو عدد گنگ، عددی گنگ است.\n\n۴) بین دو کسر $\\frac12$ و $\\frac13$ بی‌شمار عدد گنگ وجود دارد.",
   options=["۴", "۳", "۲", "۱"],
   solution=ans(4, "۱ و ۳ با مثال نقض $\\sqrt2$ و $-\\sqrt2$ یا $\\sqrt2\\times\\sqrt2$ نادرست‌اند. ۲ نادرست است. ۴ درست است. پس فقط ۱ جمله درست است.")),
 "g9_sets_043": dict(status="pending", answer=1,
   stem="کسر عدد $2.0\\overline{29}$ کدام است؟",
   options=["$\\frac{2009}{990}$", "$\\frac{2009}{999}$", "$\\frac{2009}{900}$", "$\\frac{2029}{999}$"],
   solution=ans(1, "عدد متناوب مرکب است: (کل رقم‌ها منهای رقم‌های غیرتکراری) تقسیم بر (دو ۹ برای دورهٔ دورقمی و یک ۰ برای رقم غیرتکراری): $\\frac{2029-20}{990}=\\frac{2009}{990}$."),
   note="دو خوانش مختلف از صورت سؤال داشتم ($2.0\\overline{29}$ یا $2.\\overline{029}$)؛ فقط اولی با گزینه‌ها جور درمی‌آید. با اسکن مقایسه کنید."),
 "g9_sets_044": dict(status="approved", answer=1,
   stem="کدام کسر، متناوب مرکب است؟",
   options=["$\\frac{16}{45}$", "$\\frac23$", "$\\frac48$", "$\\frac{4}{33}$"],
   solution=ans(1, "مخرج $45=9\\times5$ هم عامل ۳ دارد هم عامل ۵، پس اعشار متناوب مرکب است ($0.3\\overline{5}$). $\\frac23=0.\\overline6$ و $\\frac4{33}=0.\\overline{12}$ متناوب ساده‌اند و $\\frac48=0.5$ مختوم است.")),
 "g9_sets_045": dict(status="approved", answer=3,
   stem="علی کاری را در ۸ ساعت و رضا همان کار را در ۱۲ ساعت انجام می‌دهد. دو نفر با هم کار را در چه مدتی انجام می‌دهند؟",
   options=["۴٫۵ ساعت", "۴٫۶ ساعت", "۴٫۸ ساعت", "۴٫۲ ساعت"],
   solution=ans(3, "در یک ساعت $\\frac18+\\frac1{12}=\\frac5{24}$ کار انجام می‌شود، پس کل کار $\\frac{24}{5}=4.8$ ساعت طول می‌کشد.")),
 "g9_sets_046": dict(status="approved", answer=2, concept_id="G9_RIAZI_ch2_l2_k2",
   stem="اگر شعاع دایره عددی گویا باشد، عددی که محیط دایره را بیان می‌کند: (تیزهوشان و نمونه دولتی کرمانشاه ۹۳–۹۲)",
   options=["گویا است", "گنگ است", "صحیح است", "مربع کامل است"],
   solution=ans(2, "محیط $2\\pi r$ است. حاصل‌ضرب عدد گویای ناصفر $2r$ در عدد گنگ $\\pi$ همواره گنگ است.")),
 "g9_sets_047": dict(status="approved", answer=1,
   stem="کسر عدد $5.\\overline{005}$ را به دست آورید.",
   options=["$\\frac{5000}{999}$", "$\\frac{5005}{999}$", "$\\frac{5000}{1000}$", "$\\frac{5000}{900}$"],
   solution=ans(1, "$x=5.\\overline{005}\\Rightarrow1000x=5005.\\overline{005}\\Rightarrow999x=5000\\Rightarrow x=\\frac{5000}{999}$.")),
 "g9_sets_049": dict(status="approved", answer=2,
   stem="کدام گزینه صحیح است؟ (تیزهوشان و نمونه دولتی کرمانشاه ۹۳–۹۲)",
   options=["مربع هر عدد صحیح، عددی طبیعی است.", "هر عدد مرکب، عددی حقیقی است.", "حاصل جمع دو عدد گنگ نمی‌تواند عددی گویا باشد.", "اگر هر عدد اولی را با یک جمع کنیم، عددی مرکب می‌شود."],
   solution=ans(2, "۱) مربع صفر طبیعی نیست. ۲) هر عدد طبیعی حقیقی است، پس درست است. ۳) $\\sqrt2+(-\\sqrt2)=0$. ۴) $2+1=3$ اول است.")),
 "g9_sets_050": dict(status="approved", answer=3,
   stem="اگر $a$ گنگ و $b$ گویا باشد، کدام گزینه ممکن است گنگ نباشد؟ (تیزهوشان و نمونه دولتی قم ۹۳–۹۲)",
   options=["$\\frac1a$", "$a-b$", "$ab$", "$a+b$"],
   solution=ans(3, "وارون، تفاضل و مجموع یک گنگ با یک گویا همیشه گنگ‌اند. اما اگر $b=0$ باشد، $ab=0$ گویاست.")),
 "g9_sets_051": dict(status="approved", answer=4,
   stem="نمایش اعشاری کدام یک از کسرهای زیر، متناوب ساده است؟",
   options=["$\\frac{16}{45}$", "$\\frac76$", "$\\frac18$", "$\\frac23$"],
   solution=ans(4, "$\\frac{16}{45}=0.3\\overline5$ و $\\frac76=1.1\\overline6$ متناوب مرکب‌اند، $\\frac18=0.125$ مختوم است و $\\frac23=0.\\overline6$ متناوب ساده است.")),
 "g9_sets_052": dict(status="approved", answer=1,
   stem="کدام گزینه نادرست است؟ (تیزهوشان و نمونه دولتی آذربایجان غربی، شرقی، اردبیل و زنجان ۹۳–۹۲)",
   options=["مجموع دو عدد گنگ، همیشه گنگ است.", "مجموع دو عدد گویا، همیشه گویا است.", "حاصل‌ضرب یک عدد گویا و یک عدد گنگ می‌تواند گویا باشد.", "حاصل‌ضرب دو عدد گنگ می‌تواند گویا باشد."],
   solution=ans(1, "$\\sqrt2+(-\\sqrt2)=0$ گویاست، پس گزینهٔ ۱ نادرست است. گزینهٔ ۲ درست است. در گزینهٔ ۳ اگر عدد گویا صفر باشد حاصل‌ضرب گویاست. در گزینهٔ ۴ $\\sqrt2\\times\\sqrt2=2$.")),
 "g9_sets_053": dict(status="approved", answer=4,
   stem="حاصل عبارت $\\frac{1}{11\\times16}+\\frac{1}{16\\times21}+\\frac{1}{21\\times26}+\\cdots+\\frac{1}{46\\times51}$ برابر است با: (روبوکاپ، دهمین دوره ۱۳۹۴)",
   options=["$\\frac{8}{2805}$", "$\\frac{62}{561}$", "$\\frac{40}{561}$", "$\\frac{8}{561}$"],
   solution=ans(4, "$\\frac{1}{n(n+5)}=\\frac15\\left(\\frac1n-\\frac1{n+5}\\right)$؛ جمله‌ها حذف می‌شوند و $\\frac15\\left(\\frac1{11}-\\frac1{51}\\right)=\\frac15\\times\\frac{40}{561}=\\frac{8}{561}$.")),
 "g9_sets_056": dict(status="pending", answer=2,
   stem="در شکل زیر نقطهٔ $M$ چه عددی را نشان می‌دهد؟ (اندازهٔ پاره‌خط‌های عمودی یک واحد است) (تیزهوشان و نمونه دولتی سمنان، مازندران و تهران ۹۳–۹۲)",
   options=["$\\sqrt5-\\sqrt2$", "$\\sqrt3$", "$\\sqrt5-1$", "$\\sqrt2$"],
   solution=ans(2, "مثلث اول وتر $\\sqrt{1^2+1^2}=\\sqrt2$ دارد. مثلث دوم روی این وتر با ارتفاع ۱ وتر $\\sqrt{(\\sqrt2)^2+1^2}=\\sqrt3$ دارد و کمانی به همین شعاع نقطهٔ $M$ را می‌سازد: $M=\\sqrt3$."),
   note="گزینه‌ها و راه‌حل از روی شکل بازنویسی شد؛ شکل را با اسکن مقایسه کنید."),
 "g9_sets_057": dict(status="approved", answer=2,
   stem="صورت کسرهای ساده‌نشدنی زیر عددی طبیعی است. نمایش اعشاری کدام یک از آن‌ها متناوب است؟ (نمونه دولتی خراسان جنوبی ۹۶–۹۵)",
   options=["$\\frac{a}{80}$", "$\\frac{b}{120}$", "$\\frac{c}{160}$", "$\\frac{d}{400}$"],
   solution=ans(2, "کسر ساده‌نشدنی وقتی مختوم است که مخرجش فقط عامل‌های ۲ و ۵ داشته باشد. $80$، $160$ و $400$ فقط ۲ و ۵ دارند؛ اما $120=2^3\\times3\\times5$ عامل ۳ دارد و چون کسر ساده نمی‌شود، متناوب است.")),
 "g9_sets_058": dict(status="pending", answer=3,
   stem="در شکل زیر میانگین عددهای متناظر با نقطه‌های $A$ و $B$ چه عددی است؟ (تیزهوشان و نمونه دولتی تهران ۹۳–۹۲)",
   options=["$\\frac{\\sqrt{13}-\\sqrt{10}}{2}$", "$\\frac{\\sqrt{10}+\\sqrt{13}}{2}$", "$\\frac{\\sqrt{10}-\\sqrt{13}}{2}$", "$\\frac{-\\sqrt{13}-\\sqrt{10}}{2}$"],
   solution=ans(3, "$A=1-\\sqrt{13}$ و $B=-1+\\sqrt{10}$. میانگین: $\\frac{(1-\\sqrt{13})+(-1+\\sqrt{10})}{2}=\\frac{\\sqrt{10}-\\sqrt{13}}{2}$."),
   note="مختصات نقطه‌ها از روی شکل خوانده شد؛ شکل را با اسکن مقایسه کنید."),
 "g9_sets_059": dict(status="approved", answer=2,
   stem="کدام کسر با عدد اعشاری $5.666\\ldots$ برابر است؟ (نمونه دولتی قم ۹۶–۹۵)",
   options=["$\\frac{19}{3}$", "$\\frac{17}{3}$", "$\\frac{16}{3}$", "$\\frac{5}{3}$"],
   solution=ans(2, "$x=5.\\overline6\\Rightarrow10x=56.\\overline6\\Rightarrow9x=51\\Rightarrow x=\\frac{17}{3}$.")),
}

# not corrected, but not safe to serve until the manager has compared them with the scan
HOLD = {
 "g9_sets_008": "نمودارها را با اسکن مقایسه کنید؛ دو خوانش متفاوت از عبارت ($A-(A\\cap B)$ یا $(A\\cap B)-A$) دارم.",
 "g9_sets_015": "صورت سؤال با اسکن نمی‌خواند (مجموعه‌های داده‌شده و ؟ خوانده نشد).",
 "g9_sets_016": "نمودارهای گزینه‌ها را با اسکن مقایسه کنید؛ دو گزینه به نظر یکسان بودند.",
 "g9_sets_021": "صورت سؤال ناقص است (توضیح تاس و حالت‌ها در اسکن هست ولی خوانده نشد).",
 "g9_sets_025": "هر دو گزینهٔ ۲ و ۴ درست به نظر می‌رسند؛ با اسکن مقایسه کنید.",
 "g9_sets_041": "شکل و گزینه‌ها با اسکن نمی‌خوانند.",
 "g9_sets_054": "گزینه‌ها و راه‌حل با اسکن نمی‌خوانند.",
 "g9_sets_060": "دو خوانش از اسکن ($\\sqrt5$ یا $\\sqrt6$) نتیجهٔ متفاوت می‌دهد؛ با اسکن مقایسه کنید.",
}
REJECT = {
 "g9_sets_055": "تکراری سؤال ۴۲ است (همان چهار عبارت).",
}


def bank_dirs(root: str) -> dict:
    """public id (folder name) -> folder path, for every question folder under root"""
    out = {}
    for dirpath, _dirs, files in os.walk(root):
        if "meta.json" in files:
            out[os.path.basename(dirpath)] = dirpath
    return out


def write_files(root: str, write: bool):
    """The files are the source of truth: a fresh database imports from them, so the
    corrections must live there too (a re-import would otherwise bring the errors back)."""
    folders = bank_dirs(root)
    done = 0
    for pid, c in C.items():
        path = folders.get(pid)
        if not path:
            print("no folder for", pid)
            continue
        meta_file = os.path.join(path, "meta.json")
        meta = json.load(open(meta_file, encoding="utf-8"))
        n = "".join(ch for ch in pid.rsplit("_", 1)[-1] if ch.isdigit()).lstrip("0") or "0"
        opts = "\n\n".join(f"{i}) {o}" for i, o in enumerate(c["options"], 1))
        qmd = f"# سؤال {n}\n\n{c['stem']}\n\n{opts}\n"
        meta.update({"options": c["options"], "answer_option": c["answer"],
                     "answer_confidence": "high",
                     "needs_answer_verification": c["status"] != "approved",
                     "verification": {"status": "verified" if c["status"] == "approved" else "needs_fix",
                                      "key_option": c["answer"], "solver_option": c["answer"],
                                      "notes": ["corrected from the scan, see scripts/apply_corrections.py"]}})
        print(f"{pid}: files {'written' if write else 'would be written'}")
        if write:
            open(os.path.join(path, "question.md"), "w", encoding="utf-8", newline="\n").write(qmd)
            open(os.path.join(path, "answer.md"), "w", encoding="utf-8", newline="\n").write(c["solution"] + "\n")
            json.dump(meta, open(meta_file, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=2)
        done += 1
    for pid, note in HOLD.items():
        path = folders.get(pid)
        if path and write:
            meta_file = os.path.join(path, "meta.json")
            meta = json.load(open(meta_file, encoding="utf-8"))
            meta["needs_answer_verification"] = True
            meta["audit_note"] = note
            json.dump(meta, open(meta_file, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=2)
    print(f"{done} question folders", "updated" if write else "checked (dry run)")


def main(write: bool):
    now = clock.now_utc()
    counts = {"approved": 0, "pending": 0, "rejected": 0, "missing": 0}

    def apply(pid, update, action, note=None):
        q = db.db.questions.find_one({"public_id": pid}, {"_id": 1})
        if not q:
            counts["missing"] += 1
            print("missing:", pid)
            return
        counts[update.get("review_status", "pending")] += 1
        print(f"{pid}: -> {update.get('review_status')}")
        if write:
            db.db.questions.update_one(
                {"public_id": pid},
                {"$set": {**update, "edited_by": BY, "edited_at": now},
                 "$push": {"history": {"action": action, "by": BY, "at": now, "note": note}}})

    for pid, c in C.items():
        upd = {"stem_md": c["stem"], "options": c["options"], "answer": {"option": c["answer"]},
               "solution_md": c["solution"], "answer_confidence": "high",
               "verification": {"status": "verified" if c["status"] == "approved" else "needs_fix",
                                "key_option": c["answer"], "solver_option": c["answer"],
                                "notes": ["بازبینی با اسکن و حل دستی در ۱۴۰۵/۰۸/۲۶"]},
               "needs_answer_verification": c["status"] != "approved",
               "review_status": c["status"], "reviewed": c["status"] == "approved",
               "reviewed_by": BY, "reviewed_at": now, "rejection_note": None}
        if c.get("concept_id"):
            concept = db.db.concepts.find_one({"concept_id": c["concept_id"]})
            if not concept:
                raise SystemExit(f"unknown concept {c['concept_id']}")
            upd.update({"concept_id": concept["concept_id"], "book_id": concept.get("book_id"),
                        "chapter_id": concept.get("chapter_id")})
        if c["status"] == "pending":
            upd["audit_note"] = c.get("note")
        apply(pid, upd, "corrected_from_scan", c.get("note"))
    for pid, note in HOLD.items():
        apply(pid, {"review_status": "pending", "reviewed": False,
                    "needs_answer_verification": True, "audit_note": note}, "held_for_review", note)
    for pid, note in REJECT.items():
        apply(pid, {"review_status": "rejected", "reviewed": False, "rejection_note": note},
              "rejected", note)
    print(counts, "(dry run, nothing written)" if not write else "(written)")


if __name__ == "__main__":
    # python -m scripts.apply_corrections --files <question_bank dir> [--write]
    if "--files" in sys.argv:
        write_files(sys.argv[sys.argv.index("--files") + 1], "--write" in sys.argv)
    else:
        main("--write" in sys.argv)
