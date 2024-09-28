import http from 'http';
import { GoogleGenerativeAI } from "@google/generative-ai";

const API_KEY = 'AIzaSyAlWv9StZc6SR5dmmidAsr-ZypraVx6w7g';
const genAI = new GoogleGenerativeAI(API_KEY);

const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }

  if (req.method === 'POST' && req.url === '/ajax') {
    let data = '';

    req.on('data', chunk => {
      data += chunk;
    });

    req.on('end', () => {
      console.log('Received data:', data);

      res.writeHead(200, { 'Content-Type': 'application/json' });

      const model = genAI.getGenerativeModel({ model: "gemini-pro" });
      const prompt = data;
      
      model.generateContent(prompt)
        .then(result => {
          const response = result.response;
          const generatedText = response.text();
          console.log(generatedText);

          res.end(JSON.stringify({ message: 'Received data successfully', data: generatedText }));
        })
        .catch(error => {
          console.error('Error generating content:', error);
          res.end(JSON.stringify({ error: 'Error generating content' }));
        });
    });
  } else {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('Not Found');
  }
});

const PORT = 3001;

server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
