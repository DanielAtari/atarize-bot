// Reference global components
const HeroSection = window.HeroSection;
const ChatWidget = window.ChatWidget;
const FeaturesSection = window.FeaturesSection;
const PricingSection = window.PricingSection;
const AboutSection = window.AboutSection;
const ContactSection = window.ContactSection;

const SectionDivider = () => (
  <div className="border-t border-muted my-12 w-full max-w-3xl mx-auto" />
);

// Fade-in/slide-up animation hook
function useFadeInOnScroll() {
  const ref = React.useRef();
  const [visible, setVisible] = React.useState(false);
  React.useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new window.IntersectionObserver(
      ([entry]) => setVisible(entry.isIntersecting),
      { threshold: 0.15 }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return [ref, visible];
}

// Wrapper for animated section
const AnimatedSection = ({ children, id }) => {
  const [ref, visible] = useFadeInOnScroll();
  return (
    <section
      id={id}
      ref={ref}
      className={`transition-all duration-700 ease-out transform ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}
    >
      {children}
    </section>
  );
};

// Main App Component
const App = () => {
  return (
    <div className="min-h-screen bg-background" dir="rtl">
      {/* Navigation */}
      <nav className="border-b border-border bg-card/50 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-row justify-between items-center h-16">
            {/* Logo on the right */}
            <div className="flex items-center gap-x-2 order-1">
              <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                <i className="fas fa-robot text-primary-foreground text-sm"></i>
              </div>
              <span className="font-bold text-xl">Atarize</span>
            </div>
            {/* Navigation menu in the center with even RTL spacing */}
            <div className="hidden md:flex items-center space-x-reverse space-x-8 text-right pl-4 order-2">
              <a href="#features" className="text-foreground hover:text-primary transition-colors">תכונות</a>
              <a href="#pricing" className="text-foreground hover:text-primary transition-colors">מחירים</a>
              <a href="#about" className="text-foreground hover:text-primary transition-colors">אודות</a>
              <a href="#contact" className="text-foreground hover:text-primary transition-colors">צור קשר</a>
            </div>
            {/* CTA button on the left */}
            <div className="order-3">
              <a href="#contact">
                <button className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition-opacity">
                  התחילו עכשיו
                </button>
              </a>
            </div>
          </div>
        </div>
      </nav>
      {/* Hero Section and Chat Widget (RTL order) */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-20">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          {/* HeroSection on right, ChatWidget on left */}
          <HeroSection />
          <ChatWidget />
        </div>
        {/* Features, Pricing, About, and Contact Sections with dividers */}
        <SectionDivider />
        <AnimatedSection id="features" className="scroll-offset"><FeaturesSection /></AnimatedSection>
        <SectionDivider />
        <AnimatedSection id="pricing" className="scroll-offset"><PricingSection /></AnimatedSection>
        <SectionDivider />
        <AnimatedSection id="about" className="scroll-offset"><AboutSection /></AnimatedSection>
        <SectionDivider />
        <AnimatedSection id="contact" className="scroll-offset"><ContactSection /></AnimatedSection>
      </main>
      {/* Footer */}
      <footer className="border-t border-border bg-muted/20 mt-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center text-muted-foreground">
            <p>כל הזכויות שמורות © 2024 Atarize</p>
          </div>
        </div>
      </footer>
    </div>
  );
};

// Render the app
ReactDOM.render(<App />, document.getElementById('root')); 