import React, { useState } from 'react';

const ContactSection = () => {
  const [form, setForm] = useState({ full_name: '', phone: '', email: '' });
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess(false);
    try {
      const apiUrl = window.location.hostname.includes('render')
        ? 'https://atarize-backend.onrender.com/api/contact'
        : '/api/contact';
      const res = await fetch(apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (data.success) {
        setSuccess(true);
        setForm({ full_name: '', phone: '', email: '' });
      } else {
        setError(data.error || 'אירעה שגיאה. נסו שוב.');
      }
    } catch (err) {
      setError('אירעה שגיאה. נסו שוב.');
    }
    setLoading(false);
  };

  return (
    <section id="contact" className="scroll-offset max-w-2xl mx-auto my-16 bg-card rounded-xl shadow-lg border border-border p-8 text-right">
      <h2 className="text-3xl font-bold mb-6">השאירו פרטים להתחלה</h2>
      {success ? (
        <div className="text-green-600 font-semibold text-lg py-4">תודה! נחזור אליכם בקרוב.</div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block mb-1 font-medium">שם מלא</label>
            <input
              type="text"
              name="full_name"
              value={form.full_name}
              onChange={handleChange}
              required
              className="w-full px-4 py-3 border border-border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label className="block mb-1 font-medium">טלפון</label>
            <input
              type="tel"
              name="phone"
              value={form.phone}
              onChange={handleChange}
              required
              className="w-full px-4 py-3 border border-border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label className="block mb-1 font-medium">אימייל</label>
            <input
              type="email"
              name="email"
              value={form.email}
              onChange={handleChange}
              required
              className="w-full px-4 py-3 border border-border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          {error && <div className="text-red-600 font-medium">{error}</div>}
          <button
            type="submit"
            className="w-full py-3 bg-primary text-primary-foreground rounded-lg font-bold text-lg hover:opacity-90 transition-opacity"
            disabled={loading}
          >
            {loading ? 'שולח...' : 'שלח'}
          </button>
        </form>
      )}
    </section>
  );
};

export default ContactSection; 