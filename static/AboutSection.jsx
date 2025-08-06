import React from 'react';

const AboutSection = () => (
  <section id="about" className="scroll-offset max-w-3xl mx-auto my-16 bg-card rounded-xl shadow-lg border border-border p-8 text-right">
    <h2 className="text-3xl font-bold mb-8">על Atarize</h2>
    <p className="mb-4">Atarize היא פלטפורמה לבניית צ'אטבוטים חכמים ומותאמים אישית לעסקים בישראל. מבוסס GPT + Vector DB.</p>
    <h3 className="text-xl font-semibold mb-2">מה אנחנו עושים:</h3>
    <ul className="list-disc pr-6 mb-4 space-y-1">
      <li>בוט מבוסס תוכן שיווקי וקבצים</li>
      <li>התאמת טון דיבור לעסק</li>
      <li>איסוף לידים משיחה טבעית</li>
      <li>הטמעה באתר או לינק לוואטסאפ</li>
    </ul>
    <h3 className="text-xl font-semibold mb-2">מה חשוב לדעת:</h3>
    <ul className="list-disc pr-6 mb-4 space-y-1">
      <li>אין צורך באפליקציה</li>
      <li>אין צורך בהבנה טכנית</li>
      <li>לא כולל אינטגרציות (CRM / סליקה)</li>
    </ul>
    <h3 className="text-xl font-semibold mb-2">מטרתנו:</h3>
    <p className="mb-4">לחסוך זמן, לשפר שירות, להפוך עמודים לכלי מכירה 24/7 – בלי כח אדם.</p>
    <h3 className="text-xl font-semibold mb-2">תהליך עבודה:</h3>
    <ol className="list-decimal pr-6 mb-4 space-y-1">
      <li>בוחרים ידע לבוט</li>
      <li>מעלים טקסט/קובץ</li>
      <li>מקבלים קישור אישי</li>
    </ol>
    <h3 className="text-xl font-semibold mb-2">שאלות נפוצות:</h3>
    <ul className="list-disc pr-6 space-y-1">
      <li><b>עלות הקמה?</b> ₪390 מחיר השקה (במקום ₪690). הטמעה: ₪200</li>
      <li><b>זמן אספקה?</b> 2–5 ימי עסקים</li>
      <li><b>מה כוללות חבילות?</b> לפי הודעות (Basic / Standard / Pro)</li>
      <li><b>שינוי תוכן?</b> כן, עדכונים קטנים כלולים</li>
      <li><b>תשלום?</b> הקמה + מנוי. אשראי/ביט/העברה</li>
    </ul>
  </section>
);

export default AboutSection; 