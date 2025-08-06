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
            <td><s>₪690</s> ₪390 (מחיר הרצה)</td>
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
            <td>עד 300</td>
            <td>₪119</td>
            <td>עסקים קטנים</td>
          </tr>
          <tr>
            <td>Standard</td>
            <td>עד 1,000</td>
            <td>₪399</td>
            <td>עסקים בינוניים</td>
          </tr>
          <tr>
            <td>Pro</td>
            <td>עד 3,000</td>
            <td>₪1,190</td>
            <td>מותגים עם תנועה גבוהה</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div className="text-sm text-muted-foreground mt-4 p-4 bg-muted/50 rounded-lg">
      <strong>סה"כ הפעלה ראשונית:</strong><br/>
      מחיר רגיל: ₪890 (₪690 + ₪200)<br/>
      <span className="text-primary font-bold">מחיר השקה: ₪590 (₪390 + ₪200)</span>
    </div>
    <div className="text-lg text-primary font-bold mt-6">⚠️ מחיר השקה - ללקוחות ראשונים בלבד!</div>
  </section>
);

export default PricingSection; 