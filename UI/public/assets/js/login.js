const express = require('express');
const mongoose = require('mongoose');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const User = require('../../../../backend/user'); // Assume the User model is defined as explained before

const app = express();

// Middleware to parse JSON requests
app.use(express.json());

// MongoDB connection
mongoose.connect('mongodb+srv://breannong2023:7rgWH1qw3rgneVNZ@ticketing-db.qqamb.mongodb.net/', {
  useNewUrlParser: true,
  useUnifiedTopology: true,
})
.then(() => console.log('MongoDB connected successfully'))
.catch(err => console.log('MongoDB connection error:', err));


// POST route for login
app.post('/login', async (req, res) => {
  const { email, password } = req.body;

  // Log the incoming email and password for debugging purposes
  console.log('Received email:', email);
  console.log('Received password:', password);

  // Find the user by email
  const user = await User.findOne({ email });

  if (!user) {
    console.log('User not found in the database');
    return res.status(400).json({ message: 'Invalid email or password' });
  }

  // Check if the password is correct
  const isMatch = await bcrypt.compare(password, user.password);
  if (!isMatch) {
    console.log('Password mismatch');
    return res.status(400).json({ message: 'Invalid email or password' });
  }

  // Generate a JWT token
  const token = jwt.sign({ userId: user._id }, 'your_jwt_secret', { expiresIn: '1h' });

  // Send the token to the frontend
  res.json({ token });
});


// Start server
app.listen(5000, () => {
  console.log('Server running on port 5000');
});

