import { useState, useEffect, useMemo, useRef } from 'react';
import { motion } from 'framer-motion';
import { 
  Thermometer, Droplets, Sun, Sprout, Activity, 
  Bot, Send, Leaf, User, Lock, Loader2, ArrowRight
} from 'lucide-react';

// ==========================================
// 1. PANTALLA DE LOGIN (MEJORADA Y SIN EMOJIS)
// ==========================================
const LoginScreen = ({ onLogin }) => {
  const [usuario, setUsuario] = useState('');
  const [password, setPassword] = useState('');
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState('');

  const manejarIngreso = (e) => {
    e.preventDefault();
    setCargando(true);
    setError('');

    // Simulador de conexión al Backend
    setTimeout(() => {
      if (usuario === 'admin' && password === 'iot123') {
        onLogin();
      } else {
        setError('Credenciales incorrectas. Verifique e intente nuevamente.');
        setCargando(false);
      }
    }, 1500);
  };

  return (
    <div className="flex h-screen w-full bg-white font-sans overflow-hidden">
      
      {/* Mitad Izquierda: Imagen Local con Filtro Corporativo */}
      <div className="hidden lg:flex w-1/2 relative bg-emerald-950">
        <img 
          src="/fondo-login.jpg" 
          alt="Fondo botánico" 
          className="absolute inset-0 w-full h-full object-cover opacity-60 mix-blend-overlay"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-emerald-950 via-emerald-950/50 to-transparent"></div>
        
        <div className="relative z-10 flex flex-col justify-end p-16 h-full text-white">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 1 }}>
            <div className="bg-white/10 backdrop-blur-md p-4 rounded-2xl w-fit mb-8 border border-white/20 shadow-xl">
              <Leaf size={40} className="text-emerald-400" />
            </div>
            <h1 className="text-5xl font-extrabold mb-4 leading-tight tracking-tight drop-shadow-md">
              Agro-Inteligencia<br/>en Tiempo Real
            </h1>
            <p className="text-lg text-emerald-50/90 max-w-md font-medium leading-relaxed">
              Plataforma de monitoreo de precisión impulsada por arquitectura FIWARE y modelos de predicción automatizados.
            </p>
          </motion.div>
        </div>
      </div>

      {/* Mitad Derecha: Formulario Ultra Clean UI */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 bg-[#f8faf9]">
        <motion.div 
          initial={{ opacity: 0, x: 20 }} 
          animate={{ opacity: 1, x: 0 }} 
          className="w-full max-w-md bg-white p-10 rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-gray-100"
        >
          <div className="text-center mb-10">
            <h2 className="text-3xl font-extrabold text-gray-800 tracking-tight">Acceso al Sistema</h2>
            <p className="text-gray-500 mt-2 text-sm">Ingrese sus credenciales de administrador</p>
          </div>

          <form onSubmit={manejarIngreso} className="space-y-6">
            
            <div className="space-y-2">
              <label className="text-xs font-bold text-gray-600 uppercase tracking-wider ml-1">Usuario</label>
              <div className="relative flex items-center">
                <User className="absolute left-4 text-gray-400" size={18} />
                <input 
                  type="text" 
                  required
                  value={usuario}
                  onChange={(e) => setUsuario(e.target.value)}
                  className="w-full bg-gray-50/50 border border-gray-200 text-gray-800 rounded-xl py-3.5 pl-12 pr-4 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 focus:bg-white transition-all text-sm font-medium"
                  placeholder="admin"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-bold text-gray-600 uppercase tracking-wider ml-1">Contraseña</label>
              <div className="relative flex items-center">
                <Lock className="absolute left-4 text-gray-400" size={18} />
                <input 
                  type="password" 
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-gray-50/50 border border-gray-200 text-gray-800 rounded-xl py-3.5 pl-12 pr-4 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 focus:bg-white transition-all text-sm font-medium"
                  placeholder="••••••••"
                />
              </div>
            </div>

            {error && (
              <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="bg-red-50 text-red-600 p-3 rounded-lg text-sm font-medium border border-red-100 text-center">
                {error}
              </motion.div>
            )}

            <button 
              type="submit" 
              disabled={cargando}
              className="w-full bg-emerald-600 text-white font-bold rounded-xl py-4 mt-2 hover:bg-emerald-700 active:scale-[0.98] transition-all shadow-lg shadow-emerald-600/20 flex justify-center items-center gap-2"
            >
              {cargando ? (
                <> <Loader2 className="animate-spin" size={20} /> Autenticando... </>
              ) : (
                <> Ingresar al Dashboard <ArrowRight size={18} /> </>
              )}
            </button>
          </form>
        </motion.div>
      </div>
    </div>
  );
};


// ==========================================
// 2. COMPONENTE DEL DASHBOARD (CULTIVO)
// ==========================================

const calcularSalud = (temp, hum_tierra, luz) => {
  let puntos = 100;
  if (temp > 30 || temp < 15) puntos -= 20;
  if (temp > 35 || temp < 10) puntos -= 20;
  if (hum_tierra < 40) puntos -= (40 - hum_tierra) * 2; 
  if (luz < 30) puntos -= 15;
  return Math.max(0, Math.min(100, puntos)); 
};

const MetricCard = ({ title, value, unit, icon: Icon, colorClass }) => {
  return (
    <motion.div whileHover={{ y: -4 }} className="bg-white p-5 rounded-[1.5rem] shadow-[0_4px_20px_rgb(0,0,0,0.03)] border border-gray-100 flex flex-col justify-between gap-4">
      <div className="flex items-center gap-3">
        <div className={`p-3 rounded-xl ${colorClass} text-white shadow-sm`}><Icon size={20} /></div>
        <p className="text-gray-500 font-semibold text-sm leading-tight">{title}</p>
      </div>
      <div className="flex items-baseline gap-1 mt-2">
        <span className="text-4xl font-extrabold text-gray-800">{value}</span>
        <span className="text-md font-bold text-gray-400">{unit}</span>
      </div>
    </motion.div>
  );
};

const Dashboard = () => {
  const [datos, setDatos] = useState({ temp: 24, hum_aire: 60, hum_tierra: 71, luz: 78 });
  const [inputText, setInputText] = useState('');
  const [mensajes, setMensajes] = useState([{ id: 1, sender: 'ai', text: 'Sistema de telemetría iniciado. Asistente en línea. ¿En qué le puedo asistir con este cultivo?' }]);
  const chatEndRef = useRef(null);

  useEffect(() => {
    const intervalo = setInterval(() => {
      setDatos(prev => ({
        ...prev,
        hum_tierra: prev.hum_tierra > 15 ? prev.hum_tierra - 0.5 : 15, 
        temp: prev.temp + (Math.random() * 0.4 - 0.2)
      }));
    }, 3000);
    return () => clearInterval(intervalo);
  }, []);

  useEffect(() => chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }), [mensajes]);

  const saludGlobal = useMemo(() => calcularSalud(datos.temp, datos.hum_tierra, datos.luz), [datos]);

  const enviarMensajeIA = () => {
    if (!inputText.trim()) return;
    const nuevoMensajeUsuario = { id: Date.now(), sender: 'user', text: inputText };
    setMensajes(prev => [...prev, nuevoMensajeUsuario]);
    const query = inputText.toLowerCase();
    setInputText('');

    setTimeout(() => {
      let respuestaIA = "Procesando telemetría... Consulte sobre variables de riego, temperatura o viabilidad general.";
      if (query.includes('agua') || query.includes('humedad') || query.includes('riego') || query.includes('regar')) {
        respuestaIA = datos.hum_tierra < 40 
          ? `ALERTA: Nivel de humedad en sustrato al ${datos.hum_tierra.toFixed(0)}%. Se requiere activación inmediata de electroválvulas.`
          : `Sustrato en rango óptimo (${datos.hum_tierra.toFixed(0)}%). No se requiere irrigación adicional.`;
      } else if (query.includes('calor') || query.includes('temperatura') || query.includes('clima')) {
        respuestaIA = `Lectura térmica actual: ${datos.temp.toFixed(1)}°C. Las condiciones atmosféricas se encuentran dentro de los márgenes de seguridad.`;
      } else if (query.includes('salud') || query.includes('estado') || query.includes('como esta')) {
        respuestaIA = `Índice de viabilidad del cultivo: ${Math.round(saludGlobal)}%. ` + 
                      (saludGlobal > 80 ? 'No se detectan anomalías fisiológicas.' : 'Se detecta un patrón de estrés hídrico potencial.');
      }
      setMensajes(prev => [...prev, { id: Date.now() + 1, sender: 'ai', text: respuestaIA }]);
    }, 1000);
  };

  const escalaPlanta = saludGlobal / 100 * 0.1 + 0.9; 
  const rotacionPlanta = (100 - saludGlobal) * 0.15; 
  const filtroColor = `grayscale(${100 - saludGlobal}%) sepia(${(100 - saludGlobal) * 0.8}%) brightness(${saludGlobal < 50 ? 0.8 : 1})`;

  return (
    <div className="flex h-screen w-full bg-[#f4f7f5] font-sans overflow-hidden">
      <main className="flex-1 flex flex-col h-full overflow-y-auto">
        <div className="p-6 md:p-8 xl:p-10 flex-1 flex flex-col h-full max-w-[1600px] mx-auto w-full">
          
          <header className="mb-8 flex flex-col sm:flex-row sm:justify-between sm:items-end gap-4 shrink-0">
            <div className="flex items-center gap-4">
              <div className="hidden sm:flex bg-emerald-600 text-white p-3 rounded-2xl shadow-lg shadow-emerald-600/30">
                <Leaf size={32} />
              </div>
              <div>
                <h2 className="text-3xl md:text-4xl font-extrabold text-gray-800 tracking-tight">Monitor Activo: Tomate</h2>
                <p className="text-emerald-600 font-semibold mt-2 flex items-center gap-2">
                  <Activity size={18} className="animate-pulse"/> Transmisión en línea • Viabilidad: {Math.round(saludGlobal)}%
                </p>
              </div>
            </div>
            <div className="hidden sm:block">
              <span className="bg-white border border-gray-200 text-gray-700 px-5 py-2.5 rounded-full font-bold text-sm shadow-sm flex items-center gap-2">
                <span className="w-2.5 h-2.5 bg-emerald-500 rounded-full animate-ping absolute"></span>
                <span className="w-2.5 h-2.5 bg-emerald-500 rounded-full relative"></span>
                Conexión FIWARE
              </span>
            </div>
          </header>

          <div className="grid grid-cols-1 xl:grid-cols-12 gap-8 flex-1 min-h-0">
            
            <div className="xl:col-span-4 bg-gradient-to-br from-emerald-500 to-teal-700 rounded-[2.5rem] flex flex-col items-center justify-center relative shadow-xl shadow-emerald-600/20 overflow-hidden min-h-[500px] xl:min-h-0 border-4 border-white">
              <div className="absolute top-[-10%] right-[-10%] w-64 h-64 bg-white/10 rounded-full blur-3xl"></div>
              <motion.img 
                src="/planta.png" 
                alt="Planta de Tomate"
                className="w-full max-w-[350px] xl:max-w-[450px] drop-shadow-2xl object-contain z-10"
                animate={{ scale: escalaPlanta, rotateZ: rotacionPlanta, y: saludGlobal < 50 ? 30 : 0 }}
                style={{ filter: filtroColor }}
                transition={{ duration: 2, ease: "easeOut" }}
              />
              <motion.div className="absolute bottom-8 bg-white/95 backdrop-blur-md px-6 py-3.5 rounded-2xl shadow-lg z-20 flex items-center gap-3" animate={{ y: [0, -5, 0] }} transition={{ repeat: Infinity, duration: 4 }}>
                <div className={`w-3 h-3 rounded-full ${saludGlobal > 80 ? 'bg-emerald-500' : saludGlobal > 40 ? 'bg-yellow-500' : 'bg-red-500'}`}></div>
                <p className="text-sm font-bold text-gray-800 tracking-wide uppercase">{saludGlobal > 80 ? 'Estado: Óptimo' : saludGlobal > 40 ? 'Estado: Riesgo Hídrico' : 'Estado: Crítico'}</p>
              </motion.div>
            </div>

            <div className="xl:col-span-8 flex flex-col gap-8 h-full min-h-0">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 shrink-0">
                <MetricCard title="Humedad Suelo" value={datos.hum_tierra.toFixed(0)} unit="%" icon={Sprout} colorClass={datos.hum_tierra > 40 ? "bg-emerald-500" : "bg-red-500"} />
                <MetricCard title="Temp. Aire" value={datos.temp.toFixed(1)} unit="°C" icon={Thermometer} colorClass={datos.temp > 15 && datos.temp < 30 ? "bg-amber-500" : "bg-red-500"} />
                <MetricCard title="Radiación Luz" value={datos.luz.toFixed(0)} unit="%" icon={Sun} colorClass="bg-blue-500" />
                <MetricCard title="Humedad Aire" value={datos.hum_aire.toFixed(0)} unit="%" icon={Droplets} colorClass="bg-cyan-500" />
              </div>

              <div className="flex-1 bg-white border border-gray-200 rounded-[2rem] shadow-[0_4px_20px_rgb(0,0,0,0.02)] flex flex-col min-h-[400px] overflow-hidden">
                <div className="bg-gray-50 px-6 py-4 border-b border-gray-100 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="bg-emerald-100 text-emerald-700 p-2.5 rounded-xl"><Bot size={22}/></div>
                    <div>
                      <h4 className="font-bold text-gray-800 text-sm">Analista IA (Módulo Local)</h4>
                      <p className="text-xs text-emerald-600 font-semibold">En línea</p>
                    </div>
                  </div>
                </div>
                
                <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-white">
                  {mensajes.map((msg) => (
                    <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`px-5 py-3 rounded-2xl max-w-[85%] text-sm leading-relaxed ${msg.sender === 'user' ? 'bg-emerald-600 text-white rounded-br-sm shadow-md shadow-emerald-600/20' : 'bg-[#f4f7f5] text-gray-700 rounded-bl-sm border border-gray-100'}`}>
                        {msg.text}
                      </div>
                    </div>
                  ))}
                  <div ref={chatEndRef} />
                </div>

                <div className="p-4 bg-white border-t border-gray-100">
                  <div className="flex gap-2 bg-gray-50 p-1.5 rounded-2xl border border-gray-200 focus-within:border-emerald-500 focus-within:ring-4 focus-within:ring-emerald-500/10 transition-all">
                    <input 
                      type="text" 
                      value={inputText}
                      onChange={(e) => setInputText(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && enviarMensajeIA()}
                      placeholder="Ingrese consulta al sistema..." 
                      className="flex-1 bg-transparent px-4 text-sm text-gray-700 focus:outline-none font-medium"
                    />
                    <button 
                      onClick={enviarMensajeIA}
                      className="bg-emerald-600 text-white p-3 rounded-xl hover:bg-emerald-700 transition-colors flex items-center justify-center shadow-md shadow-emerald-600/30"
                    >
                      <Send size={18} />
                    </button>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>
      </main>
    </div>
  );
};


// ==========================================
// 3. ENRUTADOR PRINCIPAL
// ==========================================
export default function App() {
  const [autenticado, setAutenticado] = useState(false);

  return autenticado ? (
    <Dashboard />
  ) : (
    <LoginScreen onLogin={() => setAutenticado(true)} />
  );
}