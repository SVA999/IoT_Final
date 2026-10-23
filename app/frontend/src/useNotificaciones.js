import { useCallback, useEffect, useRef, useState } from 'react';
import { getToken } from './api';

const MAX_REINTENTOS = 8;   // la reconexion NO es infinita: tras esto se muestra "caido" y se ofrece reintentar a mano
const PING_MS = 25000;      // latido para que nginx no cierre la conexion por inactividad

/**
 * WebSocket de notificaciones en vivo (predicciones del modelo).
 * Autentica enviando el token como primer mensaje. Reconecta con espera creciente hasta MAX_REINTENTOS.
 * estado: 'conectando' | 'activo' | 'caido'
 */
export function useNotificaciones({ onMensaje, onNoAutorizado }) {
  const [estado, setEstado] = useState('conectando');
  const [intento, setIntento] = useState(0); // al cambiarlo se abre una conexion nueva (reintento manual)
  const cb = useRef({ onMensaje, onNoAutorizado });

  useEffect(() => { cb.current = { onMensaje, onNoAutorizado }; });

  useEffect(() => {
    let ws;
    let latido;
    let espera;
    let cerrado = false;
    let fallos = 0;

    const conectar = () => {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      ws = new WebSocket(`${proto}://${window.location.host}/api/ws`);
      ws.onopen = () => ws.send(getToken() ?? '');
      ws.onmessage = (e) => {
        if (e.data === 'pong') return;
        let m;
        try { m = JSON.parse(e.data); } catch { return; }
        if (m.type === 'ready') {
          fallos = 0;
          setEstado('activo');
          latido = setInterval(() => ws.readyState === WebSocket.OPEN && ws.send('ping'), PING_MS);
        } else {
          cb.current.onMensaje(m);
        }
      };
      ws.onclose = (e) => {
        clearInterval(latido);
        if (cerrado) return;
        if (e.code === 4401) { cb.current.onNoAutorizado(); return; }   // token invalido o vencido
        fallos += 1;
        if (fallos > MAX_REINTENTOS) { setEstado('caido'); return; }
        setEstado('conectando');
        espera = setTimeout(conectar, Math.min(1000 * 2 ** (fallos - 1), 30000));
      };
    };

    conectar();
    return () => {
      cerrado = true;
      clearInterval(latido);
      clearTimeout(espera);
      ws?.close();
    };
  }, [intento]);

  const reintentar = useCallback(() => { setEstado('conectando'); setIntento((n) => n + 1); }, []);
  return { estado, reintentar };
}
