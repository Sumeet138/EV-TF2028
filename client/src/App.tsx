import { useEffect, useState } from 'react';

export default function App() {
  const [status, setStatus] = useState('loading...');

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then((d: { status: string }) => setStatus(d.status))
      .catch(() => setStatus('server unreachable'));
  }, []);

  return (
    <main>
      <h1>EV TF2028</h1>
      <p>API: {status}</p>
    </main>
  );
}
