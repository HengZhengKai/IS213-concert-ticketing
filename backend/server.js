const express = require('express');
const jwt = require('jsonwebtoken');
const cors = require('cors');
const axios = require('axios');

const app = express();
const PORT = 5000;

// Middleware
const corsOptions = {
  origin: ['http://localhost', 'http://127.0.0.1', 'http://localhost:5500', 'http://localhost:8080'],
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization', 'authorization']
};

app.use(cors(corsOptions));
app.use(express.json());

// Login route
app.post('/login', async (req, res) => {
  const { email, password } = req.body;

  try {
    console.log('Incoming request body:', req.body);

    // Get user from Python service using correct endpoint
    const userResponse = await axios.get(`http://localhost:5006/user/email/${email}`);
    
    if (userResponse.data.code === 404) {
      console.log('User not found:', email);
      return res.status(400).json({ message: 'Invalid email or password' });
    }

    const user = userResponse.data.data;
    console.log('User found:', user);

    // Compare the passwords (remove trailing commas from stored password)
    const storedPassword = user.password.replace(/,+$/, '');
    console.log('Comparing passwords:');
    console.log('Input password:', password);
    console.log('Stored password:', storedPassword);

    if (password === storedPassword) {
      console.log('Password match successful');
      const token = jwt.sign({ userId: user.userID }, 'your_jwt_secret', { expiresIn: '1h' });
      
      // Create a sanitized user object (removing sensitive data)
      const userData = {
        userID: user.userID,
        name: user.name,
        email: user.email,
        age: user.age,
        gender: user.gender,
        phoneNum: user.phoneNum
      };

      return res.json({ 
        token, 
        message: 'Login successful',
        user: userData
      });
    } else {
      console.log('Password mismatch');
      return res.status(400).json({ message: 'Invalid email or password' });
    }
    
  } catch (err) {
    console.error('Server error:', err);
    if (err.response) {
      console.error('Response data:', err.response.data);
    }
    res.status(500).json({ message: 'Server error', error: err.message });
  }
});

// Start server
app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});