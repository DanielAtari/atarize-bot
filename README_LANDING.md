# Atarize Smart Chatbot Landing Page

A modern, responsive landing page for the Atarize smart chatbot service, built with React and Tailwind CSS.

## Features

- **Responsive Design**: Works perfectly on desktop, tablet, and mobile devices
- **Interactive Chat Widget**: Live demo of the chatbot functionality
- **Modern UI**: Uses CSS variables and design tokens from the design system
- **React Components**: Modular component architecture

## File Structure

```
static/
├── index.html          # Main HTML entry point
├── app.jsx             # Main React application
├── HeroSection.jsx     # Hero section component
├── ChatWidget.jsx      # Interactive chat widget component
├── global.css          # CSS variables and custom styles
└── tailwind.config.js  # Tailwind CSS configuration
```

## Design System

The landing page uses the design tokens defined in `context/global.css` and `context/mcp.json`:

- **Colors**: Primary, secondary, accent, and semantic colors
- **Typography**: Poppins font family
- **Spacing**: Consistent spacing using CSS variables
- **Shadows**: Multiple shadow levels for depth
- **Border Radius**: Consistent rounded corners

## Components

### HeroSection
- Catchy headline with gradient text
- Call-to-action buttons
- Feature highlights with icons
- Responsive layout

### ChatWidget
- Interactive chat interface
- User messages on the right (as requested)
- Bot messages on the left
- Real-time message simulation
- Styled chat bubbles with 70% max-width

## How to Run

1. Start the Flask server:
   ```bash
   python app.py
   ```

2. Visit the landing page:
   ```
   http://localhost:5000/landing
   ```

3. The original chat interface is still available at:
   ```
   http://localhost:5000/
   ```

## Technical Details

- **React 18**: Using CDN version for simplicity
- **Tailwind CSS**: Configured to use custom CSS variables
- **Font Awesome**: Icons for buttons and UI elements
- **Babel**: JSX transformation in the browser

## Customization

### Colors
Edit the CSS variables in `static/global.css` to change the color scheme.

### Content
Modify the text content in `HeroSection.jsx` and `ChatWidget.jsx` to match your business needs.

### Styling
The components use Tailwind CSS classes that respect the design system. Custom styles are defined in `global.css`.

## Browser Compatibility

- Modern browsers with ES6+ support
- React 18 compatibility
- CSS Grid and Flexbox support required 