import axios from 'axios';

const TOKEN_KEY = 'tok';

export const getToken = () => sessionStorage.getItem(TOKEN_KEY);
export const setToken = (t) => sessionStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => sessionStorage.removeItem(TOKEN_KEY);

// Mismo origen: nginx hace proxy de /api hacia el servicio api (en dev lo hace vite)
const http = axios.create({ baseURL: '/api' });

http.interceptors.request.use((cfg) => {
  const t = getToken();
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

export const login = (usuario, password) =>
  http.post('/login', { usuario, password }).then((r) => r.data.token);

export const getPlantas = () => http.get('/plantas').then((r) => r.data);
export const getAlertas = (limit = 20) => http.get('/alertas', { params: { limit } }).then((r) => r.data);
export const chat = (pregunta, planta) =>
  http.post('/chat', { pregunta, planta }, { timeout: 70000 }).then((r) => r.data.respuesta);

// Para que la app cierre sesion cuando la API responde 401 (token vencido)
export const onUnauthorized = (fn) => {
  http.interceptors.response.use(
    (r) => r,
    (err) => {
      if (err.response?.status === 401) fn();
      return Promise.reject(err);
    },
  );
};
