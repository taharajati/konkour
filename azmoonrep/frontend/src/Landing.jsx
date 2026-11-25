import React, { useState } from 'react'
import { setToken } from './api'
import Login from './Login'
import { get } from './api'

export default function Landing({ onLoggedIn }) {
  const [showLogin, setShowLogin] = useState(false)
  if (showLogin) return <Login onLoggedIn={onLoggedIn} />

  return (
    <div className="landing">
      {/* ناوبری */}
      <nav className="l-nav">
        <div className="l-logo">📚 آزمون‌ریپ</div>
        <div className="l-nav-links">
          <a href="#features">امکانات</a>
          <a href="#how">چطور کار می‌کند</a>
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
            حفظ کردن جواب کتاب، سر جلسه به کارت نمی‌آید — چون سؤال با اعداد و متن جدید می‌آید.
            آزمون‌ریپ به‌جای سؤال، <b>مفهوم</b> را مرور می‌کند: هر اشتباه، همان مبحث را فردا با یک
            سؤال کاملاً تازه سراغت می‌آورد تا جایی که واقعاً بلدش باشی.
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
        <div><b>۷</b><span>کتاب رسمی درسی</span></div>
        <div><b>۳۱</b><span>فصل</span></div>
        <div><b>۱۰۰+</b><span>مبحث قابل تمرین</span></div>
        <div><b>∞</b><span>سؤال مشابه برای هر مبحث</span></div>
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
            <h3>همان سؤال، هر بار تازه</h3>
            <p>به‌جای حفظ کردن جواب، یک <b>سؤال مشابه با اعداد و متن جدید</b> می‌بینی — پس واقعاً یاد می‌گیری، نه این‌که جواب را از حفظ بشی.</p>
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
            <div className="l-f-icon">⌨️</div>
            <h3>متمرکز و سریع</h3>
            <p>یک سؤال در هر لحظه، بدون حواس‌پرتی. با کلیدهای ۱ تا ۴ جواب بده و با Enter برو جلو.</p>
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
            <p>سیستم زمان مرور هر مبحث را خودش حساب می‌کند و سؤال تازه می‌سازد. فقط بیا و جواب بده.</p>
          </div>
        </div>
      </section>

      {/* کتاب‌ها */}
      <section id="books" className="l-section">
        <h2>کتاب‌های پوشش‌داده‌شده</h2>
        <p className="l-sec-sub">رشتهٔ ریاضی و فیزیک — مطابق کتاب‌های رسمی وزارت آموزش‌وپرورش</p>
        <div className="l-books-row">
          <span className="l-book-chip">ریاضی ۱ — دهم</span>
          <span className="l-book-chip">هندسه ۱ — دهم</span>
          <span className="l-book-chip">حسابان ۱ — یازدهم</span>
          <span className="l-book-chip">هندسه ۲ — یازدهم</span>
          <span className="l-book-chip">حسابان ۲ — دوازدهم</span>
          <span className="l-book-chip">هندسه ۳ — دوازدهم</span>
          <span className="l-book-chip">آمار و احتمال — دوازدهم</span>
          <span className="l-book-chip">ریاضیات گسسته — دوازدهم</span>
        </div>
      </section>

      {/* تجربهٔ دانش‌آموز */}
      <section className="l-section l-testimonial">
        <h2>از زبان یک دانش‌آموز</h2>
        <div className="l-quote-card">
          <p className="l-quote-text">
            «من امسال نهایی یازدهم دارم و سال بعد کنکور. قبلاً از روی کتاب حل می‌کردم و فکر می‌کردم بلدم —
            تا وقتی همین سؤال‌ها با عدد جدید توی آزمون آزمایشی آمد و زدم امتحان.
            با آزمون‌ریپ هر اشتباهم می‌شود یک مرور برای فردا؛ شیمی‌ام هنوز خوب نیست ولی ریاضی‌ام دیگر دستم است.»
          </p>
          <div className="l-quote-author">
            <span className="l-quote-avatar">🧑‍🎓</span>
            <div>
              <b>امیرحسین</b> — پایهٔ یازدهم ریاضی‌فیزیک، اصفهان
              <div className="muted">هدف کنکور: مهندسی کامپیوتر شریف · رتبهٔ هدف زیر ۱۰۰۰</div>
            </div>
          </div>
        </div>
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
