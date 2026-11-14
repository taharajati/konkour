import React, { useState } from 'react'
import Login from './Login'
import Markdown from './Markdown'

const BOOKS = [
  'ریاضی نهم', 'ریاضی ۱ — دهم', 'هندسه ۱ — دهم', 'حسابان ۱ — یازدهم',
  'آمار و احتمال — یازدهم', 'حسابان ۲ — دوازدهم', 'هندسه ۳ — دوازدهم', 'ریاضیات گسسته — دوازدهم',
]

const SAMPLE = {
  stem: 'عدد اعشاری متناوب $0.\\overline{36}$ با کدام کسر برابر است؟',
  options: ['$\\frac{4}{11}$', '$\\frac{9}{25}$', '$\\frac{36}{100}$', '$\\frac{6}{11}$'],
  answer: 0,
  point: 'متناوب ساده: دوره را بر به همان تعداد ۹ تقسیم کن. $0.\\overline{36}=\\frac{36}{99}=\\frac{4}{11}$',
}

function SampleQuestion() {
  const [picked, setPicked] = useState(null)
  return (
    <div className="question-box l-sample">
      <div className="stem"><Markdown text={SAMPLE.stem} /></div>
      <div className="options" role="radiogroup" aria-label="گزینه‌ها">
        {SAMPLE.options.map((o, i) => (
          <button key={i} type="button" role="radio" aria-checked={picked === i}
                  className={`option ${picked !== null && i === SAMPLE.answer ? 'correct' : ''} ${picked === i && i !== SAMPLE.answer ? 'wrong' : ''}`}
                  onClick={() => setPicked(i)}>
            <span className="opt-num">{(i + 1).toLocaleString('fa-IR')}</span><Markdown text={o} />
          </button>
        ))}
      </div>
      {picked !== null && (
        <div className="key-point-box" aria-live="polite">
          <b>{picked === SAMPLE.answer ? '✓ درست بود.' : '✕ اشتباه بود.'} نکتهٔ این سؤال:</b>
          <Markdown text={SAMPLE.point} />
          <p className="muted">{picked === SAMPLE.answer
            ? 'چون درست زدی، این نکته سه روز دیگر برمی‌گردد، با یک سؤال دیگر.'
            : 'چون اشتباه زدی، همین امروز یک سؤال دیگر از همین نکته می‌آید و فردا دوباره.'}</p>
        </div>
      )}
    </div>
  )
}

export default function Landing({ onLoggedIn }) {
  const [showLogin, setShowLogin] = useState(false)
  if (showLogin) return <Login onLoggedIn={onLoggedIn} onBack={() => setShowLogin(false)} />

  return (
    <div className="landing">
      {/* ناوبری */}
      <nav className="l-nav">
        <div className="l-logo">📚 آزمون‌ریپ</div>
        <div className="l-nav-links">
          <a href="#features">امکانات</a>
          <a href="#how">چطور کار می‌کند</a>
          <a href="#sample">نمونه سؤال</a>
          <a href="#books">کتاب‌ها</a>
          <button className="l-cta-small" onClick={() => setShowLogin(true)}>ورود / ثبت‌نام</button>
        </div>
      </nav>

      {/* هیرو */}
      <header className="l-hero">
        <div className="l-hero-text">
          <span className="l-badge">تکرار فاصله‌دار برای ریاضی کنکور</span>
          <h1>کنکور هیچ‌وقت <span className="l-highlight">همان سؤال</span> را تکرار نمی‌کند.<br />پس چرا تو همان یک سؤال را بارها حل می‌کنی؟</h1>
          <p>
            حفظ کردن جواب کتاب سر جلسه به کارت نمی‌آید، چون سؤال با اعداد و متن جدید می‌آید.
            آزمون‌ریپ به‌جای سؤال، <b>نکته</b> را مرور می‌کند: هر اشتباه، همان نکته را با یک
            سؤال دیگر دوباره سراغت می‌آورد تا جایی که واقعاً بلدش باشی؛ و نکته‌هایی را که بلدی، با یک
            آزمون تعیین سطح کوتاه کنار می‌گذارد.
          </p>
          <div className="l-hero-actions">
            <button className="l-cta" onClick={() => setShowLogin(true)}>رایگان شروع کن</button>
            <a className="l-cta-ghost" href="#how">چطور کار می‌کند؟</a>
          </div>
          <div className="l-hero-points">
            <span>✓ بدون نیاز به کارت بانکی</span>
            <span>✓ کتاب‌های رسمی درسی</span>
            <span>✓ وب و موبایل</span>
          </div>
        </div>
        <div className="l-hero-visual">
          <div className="l-mock">
            <div className="l-mock-head">📅 جلسهٔ امروز</div>
            <div className="l-mock-line l-w70" />
            <div className="l-mock-line l-w90" />
            <div className="l-mock-stack">
              <div className="l-seg l-g" /><div className="l-seg l-o" /><div className="l-seg l-r" /><div className="l-seg l-n" />
            </div>
            <div className="l-mock-row">✓ مجموعه‌ها — مرور شد</div>
            <div className="l-mock-row">↺ مثلثات — فردا دوباره</div>
            <div className="l-mock-row l-new">★ حد و پیوستگی — مفهوم جدید</div>
            <div className="l-mock-btn">شروع جلسهٔ امروز</div>
          </div>
        </div>
      </header>

      {/* آمار */}
      <section className="l-stats">
        <div><b>۸</b><span>کتاب رسمی ریاضی، نهم تا دوازدهم</span></div>
        <div><b>۱</b><span>سؤال برای هر نکته در تعیین سطح</span></div>
        <div><b>۱ → ۳ → ۷</b><span>روز تا مرور بعدی، اگر درست بزنی</span></div>
        <div><b>٪۱۰۰</b><span>سؤال‌ها پیش از نمایش بازبینی می‌شوند</span></div>
      </section>

      {/* امکانات */}
      <section id="features" className="l-section">
        <h2>چرا آزمون‌ریپ؟</h2>
        <p className="l-sec-sub">هر چیزی که برای یک مرور مؤثر لازم داری، در یک جا</p>
        <div className="l-grid">
          <div className="l-feature">
            <div className="l-f-icon">🔁</div>
            <h3>تکرار فاصله‌دار واقعی</h3>
            <p>سؤال‌ها مثل لغت‌های زبان مرور نمی‌شوند؛ <b>مفهوم‌ها</b> مرور می‌شوند. هر بار که اشتباه جواب بدهی، فاصلهٔ مرور کوتاه‌تر و بعد از هر موفقیت طولانی‌تر می‌شود.</p>
          </div>
          <div className="l-feature">
            <div className="l-f-icon">🎲</div>
            <h3>همان نکته، سؤال دیگر</h3>
            <p>در مرور، به‌جای همان سؤال قبلی، <b>سؤال دیگری از همان نکته</b> می‌بینی؛ پس واقعاً یاد می‌گیری، نه این‌که جواب را حفظ کنی.</p>
          </div>
          <div className="l-feature">
            <div className="l-f-icon">📖</div>
            <h3>سؤال از کتاب‌های خودت</h3>
            <p>کتاب را انتخاب کن، فصل‌ها را تیک بزن. از ریاضی نهم تا حسابان دوازدهم، هندسه، آمار و احتمال و ریاضیات گسسته.</p>
          </div>
          <div className="l-feature">
            <div className="l-f-icon">📈</div>
            <h3>پیشرفت شفاف</h3>
            <p>برای هر فصل نوار پیشرفت داری: چه‌قدر یاد گرفتی، چه‌قدر نیاز به مرور داری و چه‌قدر اشتباه ماند. هیچ‌چیز پنهان نیست.</p>
          </div>
          <div className="l-feature">
            <div className="l-f-icon">🎯</div>
            <h3>دفترچهٔ اشتباهات</h3>
            <p>همهٔ سؤال‌هایی که اشتباه جواب دادی یک‌جا جمع می‌شوند تا هر وقت خواستی دوباره تمرین‌شان کنی.</p>
          </div>
          <div className="l-feature">
            <div className="l-f-icon">💡</div>
            <h3>اول درس‌نامه، بعد تست</h3>
            <p>قبل از اولین سؤال هر نکتهٔ تازه، درس‌نامهٔ چندخطی همان نکته را می‌بینی؛ و بعد از هر اشتباه دوباره یادآوری می‌شود.</p>
          </div>
        </div>
      </section>

      {/* چطور کار می‌کند */}
      <section id="how" className="l-section l-how">
        <h2>در سه قدم شروع کن</h2>
        <div className="l-steps">
          <div className="l-step">
            <span className="l-step-num">۱</span>
            <h3>کتاب‌ها را انتخاب کن</h3>
            <p>از کتاب‌های رسمی هر پایه‌ای که بخواهی — حتی پایه‌های بالاتر از خودت.</p>
          </div>
          <div className="l-step">
            <span className="l-step-num">۲</span>
            <h3>فصل‌ها را تیک بزن</h3>
            <p>برنامهٔ مرور تو فقط از فصل‌هایی می‌سازد که خودت انتخاب کرده‌ای.</p>
          </div>
          <div className="l-step">
            <span className="l-step-num">۳</span>
            <h3>هر روز جواب بده</h3>
            <p>سیستم زمان مرور هر نکته را خودش حساب می‌کند. هر روز می‌دانی چند سؤال و چند دقیقه کار داری.</p>
          </div>
        </div>
      </section>

      {/* کتاب‌ها */}
      <section id="books" className="l-section">
        <h2>کتاب‌های پوشش‌داده‌شده</h2>
        <p className="l-sec-sub">رشتهٔ ریاضی و فیزیک، مطابق کتاب‌های رسمی. بانک سؤال فصل به فصل کامل می‌شود؛ فصل‌هایی که هنوز سؤال ندارند در برنامه «به‌زودی» نشان داده می‌شوند.</p>
        <div className="l-books-row">
          {BOOKS.map(b => <span key={b} className="l-book-chip">{b}</span>)}
        </div>
      </section>

      {/* نمونه سؤال */}
      <section id="sample" className="l-section l-testimonial">
        <h2>یک سؤال امتحان کن</h2>
        <p className="l-sec-sub">همین‌طور که در اپ می‌بینی: فرمول‌ها خوانا، و بعد از جواب، نکتهٔ سؤال.</p>
        <SampleQuestion />
      </section>

      {/* CTA */}
      <section className="l-final-cta">
        <h2>امروز اولین جلسهٔ مرورت را شروع کن</h2>
        <p>چند دقیقه در روز، قبل از امتحان همه چیز فرق می‌کند.</p>
        <button className="l-cta" onClick={() => setShowLogin(true)}>همین حالا شروع کن</button>
      </section>

      <footer className="l-footer">
        <span>آزمون‌ریپ — مرور هوشمند ریاضی کنکور</span>
        <span className="muted">ساخته‌شده با ❤️ برای دانش‌آموزان ایران</span>
      </footer>
    </div>
  )
}
