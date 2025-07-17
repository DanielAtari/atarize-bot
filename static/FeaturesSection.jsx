window.FeaturesSection = () => (
  <section id="features" className="scroll-offset max-w-3xl mx-auto my-16 bg-card rounded-xl shadow-lg border border-border p-8 text-right">
    <h2 className="text-3xl font-bold mb-8">תכונות עיקריות</h2>
    <div className="overflow-x-auto">
      <table className="w-full text-right border-separate border-spacing-y-2">
        <thead>
          <tr className="text-lg font-semibold">
            <th className="pb-2">תכונה</th>
            <th className="pb-2">תיאור</th>
          </tr>
        </thead>
        <tbody className="text-base">
          <tr>
            <td>🤖 מענה אוטומטי</td>
            <td>חוסך זמן, עונה לשאלות חוזרות</td>
          </tr>
          <tr>
            <td>💬 תמיכה בשפות שונות</td>
            <td>גם ללקוחות מחו"ל</td>
          </tr>
          <tr>
            <td>🚀 התחלה מהירה</td>
            <td>מעלים מידע → מקבלים בוט</td>
          </tr>
          <tr>
            <td>📈 לידים חמים</td>
            <td>זיהוי לקוחות מתעניינים</td>
          </tr>
          <tr>
            <td>🧩 התאמה אישית</td>
            <td>טון דיבור לפי העסק</td>
          </tr>
          <tr>
            <td>🔗 גמישות בהטמעה</td>
            <td>באתר, לינק, וואטסאפ</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
); 