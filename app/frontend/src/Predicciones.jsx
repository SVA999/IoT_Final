import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { TrendingDown, Send, Info } from 'lucide-react';
import { getModeloEstado, getLecturas, getPredicciones, getNotificaciones } from './api';

const HORAS_GRAFICO = 8;
const VARIABLES = {
  soil_moisture: { etiqueta: 'Humedad del suelo', unidad: '%' },
  temperature: { etiqueta: 'Temperatura del aire', unidad: '°C' },
  humidity: { etiqueta: 'Humedad del aire', unidad: '%' },
};
// Cada estado del modelo se explica con palabras: nunca se oculta por que no hay prediccion.
const ESTADOS = {
  prediccion: ['Aviso: cruzará un límite', 'bg-red-100 text-red-700'],
  sin_riesgo: ['Sin riesgo cercano', 'bg-emerald-100 text-emerald-700'],
  estable: ['Estable', 'bg-emerald-100 text-emerald-700'],
  fuera_de_rango: ['Ya fuera de rango', 'bg-amber-100 text-amber-700'],
  datos_insuficientes: ['Datos insuficientes', 'bg-gray-100 text-gray-600'],
  sin_tendencia: ['Sin tendencia', 'bg-gray-100 text-gray-600'],
  ajuste_pobre: ['Ajuste poco confiable', 'bg-gray-100 text-gray-600'],
  datos_viejos: ['Sensor sin enviar', 'bg-gray-100 text-gray-600'],
  sin_datos: ['Sin datos', 'bg-gray-100 text-gray-600'],
};
const ENVIO = {
  enviada: ['Enviada', 'text-emerald-600'],
  pendiente: ['Pendiente', 'text-amber-600'],
  suprimida: ['No repetida', 'text-gray-400'],
  fallida: ['Falló', 'text-red-600'],
  sin_canal: ['Telegram sin configurar', 'text-gray-400'],
};
const hora = (ms) => new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
const horasTxt = (h) => (h < 1 ? `${Math.round(h * 60)} min` : `${h.toFixed(1)} h`);

// Grafico SVG sin dependencias: lecturas reales + tendencia proyectada + limite + punto de cruce estimado.
const TrendChart = ({ puntos, estado, unidad }) => {
  const W = 640, H = 230, M = { l: 46, r: 16, t: 14, b: 28 };
  if (puntos.length < 2) {
    return <div className="h-[230px] flex items-center justify-center text-sm text-gray-400">Sin suficientes lecturas en las últimas {HORAS_GRAFICO} h</div>;
  }
  const paso = Math.ceil(puntos.length / 400);
  const pts = puntos.filter((_, i) => i % paso === 0 || i === puntos.length - 1);

  const tUlt = estado?.ultima_lectura ? Date.parse(estado.ultima_lectura) : pts[pts.length - 1].t;
  const conTendencia = estado?.pendiente_h != null && estado?.valor_ajustado != null
    && ['prediccion', 'sin_riesgo', 'estable', 'fuera_de_rango'].includes(estado.estado);
  const horasProy = estado?.horas_hasta != null ? Math.min(estado.horas_hasta, 12) : 2;
  const tFin = conTendencia ? tUlt + horasProy * 3.6e6 : pts[pts.length - 1].t;
  const vFin = conTendencia ? estado.valor_ajustado + estado.pendiente_h * horasProy : null;
  const cruce = estado?.estado === 'prediccion' && estado.horas_hasta != null
    ? { t: tUlt + estado.horas_hasta * 3.6e6, v: estado.limite } : null;

  const t0 = pts[0].t;
  const ys = pts.map((p) => p.v);
  if (estado?.limite != null) ys.push(estado.limite);
  if (vFin != null) ys.push(vFin);
  let y0 = Math.min(...ys), y1 = Math.max(...ys);
  const pad = (y1 - y0 || 1) * 0.12;
  y0 -= pad; y1 += pad;

  const X = (t) => M.l + ((t - t0) / (tFin - t0 || 1)) * (W - M.l - M.r);
  const Y = (v) => H - M.b - ((v - y0) / (y1 - y0)) * (H - M.t - M.b);
  const linea = pts.map((p, i) => `${i ? 'L' : 'M'}${X(p.t).toFixed(1)},${Y(p.v).toFixed(1)}`).join(' ');
  const xt = [0, 1, 2, 3].map((i) => t0 + ((tFin - t0) * i) / 3);
  const yt = [0, 1, 2, 3].map((i) => y0 + ((y1 - y0) * i) / 3);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="Lecturas reales y tendencia proyectada">
      {yt.map((v) => (
        <g key={v}>
          <line x1={M.l} x2={W - M.r} y1={Y(v)} y2={Y(v)} stroke="#eef0ee" />
          <text x={M.l - 6} y={Y(v) + 4} textAnchor="end" fontSize="11" fill="#9ca3af">{v.toFixed(y1 - y0 < 6 ? 1 : 0)}</text>
        </g>
      ))}
      {xt.map((t) => <text key={t} x={X(t)} y={H - 8} textAnchor="middle" fontSize="11" fill="#9ca3af">{hora(t)}</text>)}
      {estado?.limite != null && (
        <g>
          <line x1={M.l} x2={W - M.r} y1={Y(estado.limite)} y2={Y(estado.limite)} stroke="#ef4444" strokeDasharray="5 4" />
          <text x={W - M.r} y={Y(estado.limite) - 5} textAnchor="end" fontSize="11" fill="#ef4444">
            {estado.limite_tipo === 'min' ? 'Mínimo' : 'Máximo'} {estado.limite}{unidad}
          </text>
        </g>
      )}
      <line x1={X(tUlt)} x2={X(tUlt)} y1={M.t} y2={H - M.b} stroke="#d1d5db" strokeDasharray="2 3" />
      <text x={X(tUlt)} y={M.t + 2} textAnchor="middle" fontSize="10" fill="#9ca3af">última lectura</text>
      <path d={linea} fill="none" stroke="#059669" strokeWidth="2" />
      <circle cx={X(pts[pts.length - 1].t)} cy={Y(pts[pts.length - 1].v)} r="3.5" fill="#059669" />
      {conTendencia && (
        <line x1={X(tUlt)} y1={Y(estado.valor_ajustado)} x2={X(tFin)} y2={Y(vFin)} stroke="#f59e0b" strokeWidth="2" strokeDasharray="6 4" />
      )}
      {cruce && (
        <g>
          <circle cx={X(cruce.t)} cy={Y(cruce.v)} r="5" fill="#ef4444" />
          <text x={X(cruce.t)} y={Y(cruce.v) + 18} textAnchor="end" fontSize="11" fontWeight="bold" fill="#ef4444">{hora(cruce.t)}</text>
        </g>
      )}
    </svg>
  );
};

const TarjetaVariable = ({ col, estado, puntos }) => {
  const meta = VARIABLES[col];
  const [txt, cls] = ESTADOS[estado?.estado] ?? ['Sin evaluar', 'bg-gray-100 text-gray-600'];
  const aviso = estado?.estado === 'prediccion';
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      className={`bg-white rounded-[1.5rem] border p-5 shadow-[0_4px_20px_rgb(0,0,0,0.03)] ${aviso ? 'border-red-300' : 'border-gray-100'}`}>
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-extrabold text-gray-800">{meta.etiqueta}</h3>
        <span className={`text-xs font-bold px-3 py-1 rounded-full ${cls}`}>{txt}</span>
      </div>
      {aviso && (
        <p className="mt-3 text-2xl font-extrabold text-red-600">
          ~{horasTxt(estado.horas_hasta)} <span className="text-base font-bold text-gray-500">
            hasta el {estado.limite_tipo === 'min' ? 'mínimo' : 'máximo'} de {estado.limite}{meta.unidad} · ≈ {hora(Date.parse(estado.ultima_lectura) + estado.horas_hasta * 3.6e6)}
          </span>
        </p>
      )}
      <p className="mt-2 text-sm text-gray-500">{estado?.detalle ?? 'El modelo aún no ha evaluado esta variable.'}</p>
      <div className="mt-3"><TrendChart puntos={puntos} estado={estado} unidad={meta.unidad} /></div>
      {estado?.n != null && (
        <p className="mt-2 text-xs text-gray-400">
          {estado.n} lecturas reales en la ventana
          {estado.r2 != null && <> · R² {estado.r2.toFixed(2)}</>}
          {estado.pendiente_h != null && <> · tendencia {estado.pendiente_h > 0 ? '+' : ''}{estado.pendiente_h.toFixed(2)} {meta.unidad}/h</>}
        </p>
      )}
    </motion.div>
  );
};

/** Pantalla "Predicciones". `tick` cambia con cada evento del websocket: asi se actualiza sin sondear. */
export default function PantallaPredicciones({ plantaId, tick }) {
  const [estados, setEstados] = useState([]);
  const [lecturas, setLecturas] = useState([]);
  const [historial, setHistorial] = useState([]);
  const [envios, setEnvios] = useState([]);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!plantaId) return undefined;
    let vivo = true;
    Promise.all([getModeloEstado(plantaId), getLecturas(plantaId, HORAS_GRAFICO), getPredicciones(168), getNotificaciones()])
      .then(([e, l, h, n]) => {
        if (!vivo) return;
        setEstados(e); setLecturas(l); setHistorial(h.filter((x) => x.entity_id === plantaId)); setEnvios(n); setError(false);
      })
      .catch(() => vivo && setError(true));
    return () => { vivo = false; };
  }, [plantaId, tick]);

  if (!plantaId) return <p className="text-gray-500">Esperando las primeras lecturas del sensor...</p>;
  const serie = (col) => lecturas.filter((r) => r[col] != null).map((r) => ({ t: Date.parse(r.ts), v: Number(r[col]) }));

  return (
    <div className="space-y-8 pb-10">
      <div className="bg-emerald-50 border border-emerald-100 rounded-2xl p-4 text-sm text-emerald-900 flex gap-3">
        <Info size={18} className="shrink-0 mt-0.5" />
        <p>
          El modelo ajusta una <b>tendencia lineal sobre las lecturas reales</b> del sensor (últimas 6 h) y estima cuándo una variable
          cruzaría su límite. <b>No inventa datos</b>: si hay pocas lecturas, mucho ruido o el sensor dejó de enviar, no predice y te dice por qué.
          La luminosidad no se modela porque es cíclica (día/noche).
        </p>
      </div>
      {error && <p className="text-red-600 text-sm">No se pudo cargar la información del modelo.</p>}

      <div className="grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-3 gap-6">
        {Object.keys(VARIABLES).map((col) => (
          <TarjetaVariable key={col} col={col} estado={estados.find((e) => e.variable === col)} puntos={serie(col)} />
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <section className="bg-white border border-gray-200 rounded-[2rem] overflow-hidden">
          <div className="bg-gray-50 px-6 py-3 border-b border-gray-100 flex items-center gap-2 text-sm font-bold text-gray-800">
            <TrendingDown size={18} className="text-emerald-600" /> Historial de avisos del modelo (7 días)
            <span className="ml-auto text-xs font-semibold text-gray-400">{historial.length}</span>
          </div>
          <ul className="max-h-72 overflow-y-auto divide-y divide-gray-50">
            {historial.length === 0 && <li className="px-6 py-4 text-sm text-gray-400">Todavía no hay avisos.</li>}
            {historial.map((p) => (
              <li key={p.id} className="px-6 py-3 text-sm">
                <p className="text-gray-700">{p.mensaje}</p>
                <p className="text-xs text-gray-400 mt-0.5">
                  generado {new Date(p.generado).toLocaleString()} · cruce estimado {new Date(p.cruce_estimado).toLocaleTimeString()}
                </p>
              </li>
            ))}
          </ul>
        </section>

        <section className="bg-white border border-gray-200 rounded-[2rem] overflow-hidden">
          <div className="bg-gray-50 px-6 py-3 border-b border-gray-100 flex items-center gap-2 text-sm font-bold text-gray-800">
            <Send size={18} className="text-sky-500" /> Avisos a Telegram
            <span className="ml-auto text-xs font-semibold text-gray-400">{envios.length}</span>
          </div>
          <ul className="max-h-72 overflow-y-auto divide-y divide-gray-50">
            {envios.length === 0 && <li className="px-6 py-4 text-sm text-gray-400">Sin avisos todavía.</li>}
            {envios.map((n) => {
              const [txt, cls] = ENVIO[n.estado] ?? [n.estado, 'text-gray-400'];
              return (
                <li key={n.id} className="px-6 py-3 text-sm flex gap-3">
                  <div className="flex-1">
                    <p className="font-semibold text-gray-800">{n.titulo}</p>
                    <p className="text-gray-600">{n.mensaje.split('\n')[0]}</p>
                    <p className="text-xs text-gray-400 mt-0.5">{new Date(n.creada).toLocaleString()}</p>
                  </div>
                  <span className={`text-xs font-bold shrink-0 ${cls}`} title={n.detalle ?? ''}>{txt}</span>
                </li>
              );
            })}
          </ul>
        </section>
      </div>
    </div>
  );
}
