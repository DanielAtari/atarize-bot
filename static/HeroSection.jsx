// HeroSection Component
window.HeroSection = () => {
  return (
    <div className="flex flex-col justify-center space-y-6 lg:space-y-8 text-right items-end">
      <div className="space-y-4">
        <h1 className="text-4xl lg:text-6xl font-bold leading-tight">
          <span className="text-black">
            צ׳אטבוט חכם
          </span>
          <br />
          מתאים לכל עסק.
        </h1>
        <p className="text-xl lg:text-2xl text-muted-foreground max-w-2xl">
          שדרגו את השירות שלכם עם שיחות מבוססות בינה מלאכותית. <br></br>
          זמין תמיד. מדוייק תמיד. ולא צריך קפה.
        </p>
      </div>
      <div className="flex flex-col sm:flex-row gap-4 justify-end">
        <button
          className="hero-button text-lg px-8 py-4"
          onClick={() => {
            const contactSection = document.getElementById('contact');
            if (contactSection) {
              contactSection.scrollIntoView({ behavior: 'smooth' });
            }
          }}
        >
          <i className="fas fa-rocket ml-2"></i>
          להשארת פרטים
        </button>
      </div>
      <div className="flex items-center space-x-reverse space-x-6 text-sm text-muted-foreground justify-end">
        <div className="flex items-center">
          <i className="fas fa-check-circle text-primary ml-2"></i>
          <span> מענה טבעי</span>
        </div>
        <div className="flex items-center">
          <i className="fas fa-check-circle text-primary ml-2"></i>
          <span>זמין 24/7</span>
        </div>
        <div className="flex items-center">
          <i className="fas fa-check-circle text-primary ml-2"></i>
          <spaמ> הטמעה פשוטה</spaמ>
        </div>
      </div>
    </div>
  );
}; 