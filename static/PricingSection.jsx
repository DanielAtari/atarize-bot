import React from 'react';

const PricingSection = () => (
  <section id="pricing" className="scroll-offset max-w-3xl mx-auto my-16 bg-card rounded-xl shadow-lg border border-border p-8 text-right">
    <h2 className="text-3xl font-bold mb-8">תמחור</h2>
    <h3 className="text-xl font-semibold mb-4">שלב ראשון: בניית הבוט</h3>
    <div className="overflow-x-auto mb-8">
      <table className="w-full text-right border-separate border-spacing-y-2">
        <thead>
          <tr className="font-semibold">
            <th className="pb-2">שירות</th>
            <th className="pb-2">מחיר</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>🔹 בנייה חד-פעמית</td>
            <td>₪600 כולל מע"מ</td>
          </tr>
          <tr>
            <td>➕ הטמעה באתר</td>
            <td>תוספת של ₪200</td>
          </tr>
        </tbody>
      </table>
    </div>
    <h3 className="text-xl font-semibold mb-4">חבילות חודשיות:</h3>
    <div className="overflow-x-auto mb-4">
      <table className="w-full text-right border-separate border-spacing-y-2">
        <thead>
          <tr className="font-semibold">
            <th className="pb-2">חבילה</th>
            <th className="pb-2">הודעות/חודש</th>
            <th className="pb-2">מחיר</th>
            <th className="pb-2">מתאים ל...</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Basic</td>
            <td>עד 100</td>
            <td>₪49</td>
            <td>עסקים קטנים</td>
          </tr>
          <tr>
            <td>Pro</td>
            <td>עד 500</td>
            <td>₪149</td>
            <td>עסקים בינוניים</td>
          </tr>
          <tr>
            <td>Business+</td>
            <td>עד 2,000</td>
            <td>₪399</td>
            <td>מותגים עם תנועה גבוהה</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div className="text-lg text-primary font-bold mt-6">📢 מבצע השקה: חודש ראשון חינם!</div>
  </section>
);

export default PricingSection; 