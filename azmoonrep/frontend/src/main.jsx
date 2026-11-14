import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { applyTheme } from './ui'

applyTheme()

ReactDOM.createRoot(document.getElementById('root')).render(<App />)
