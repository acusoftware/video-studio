export const metadata = {
  title: 'Video Studio',
  description: 'Senaryodan ücretsiz video üretimi',
};

export default function RootLayout({ children }) {
  return (
    <html lang="tr">
      <body style={{ margin: 0, fontFamily: 'system-ui, sans-serif', background: '#0f1220', color: '#e8eaf6' }}>
        {children}
      </body>
    </html>
  );
}
