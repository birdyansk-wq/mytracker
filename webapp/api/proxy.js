/**
 * Vercel serverless proxy — пересылает /api/* на внешний API
 * Установи API_URL в Vercel: Project Settings → Environment Variables
 * Пример: https://ваш-проект.railway.app
 */
export default async function handler(req, res) {
  const apiUrl = process.env.API_URL;
  if (!apiUrl) {
    return res.status(502).json({ success: false, error: 'API_URL не настроен в Vercel' });
  }

  const pathStr = String(req.query?.path || '').replace(/^\//, '');
  const targetUrl = `${apiUrl.replace(/\/$/, '')}/api/${pathStr}`;

  try {
    const options = {
      method: req.method,
      headers: {
        'Content-Type': req.headers['content-type'] || 'application/json',
      },
    };
    if (req.method !== 'GET' && req.body != null) {
      options.body = typeof req.body === 'string' ? req.body : JSON.stringify(req.body);
    }

    const response = await fetch(targetUrl, options);
    const data = await response.text();
    try {
      res.status(response.status).json(JSON.parse(data));
    } catch {
      res.status(response.status).send(data);
    }
  } catch (err) {
    console.error('Proxy error:', err);
    res.status(502).json({ success: false, error: 'Ошибка соединения с API' });
  }
}
