import { createRoot } from 'react-dom/client';
import App from './App';
import './index.css';
import './App.css';

// No StrictMode: its double mount removes the first map and kills MapLibre's shared worker pool.
createRoot(document.getElementById('root')!).render(<App />);
