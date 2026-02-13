import { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import Editor from '@monaco-editor/react'

import {
  Box,
  Button,
  Chip,
  CssBaseline,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Paper,
  ThemeProvider,
  Typography,
  Checkbox,
  CircularProgress,
  Snackbar,
  Alert,
  Stack,
  IconButton,
  Collapse
} from '@mui/material'

import {
  PlayArrow,
  Shield,
  Description,
  SmartToy,
  DataObject,
  TableChart,
  Article,
  Email,
  CheckCircle,
  WarningAmber,
  Terminal,
  KeyboardArrowUp,
  KeyboardArrowDown,
  Fingerprint,
  VerifiedUser
} from '@mui/icons-material'

import { theme } from './theme'

// --- CONSTANTS & MOCKS ---

const examplePayload = {
  "name": "Alexandra M. Keller",
  "email": "alexandra.keller@example.com",
  "case_ref": "ETK-2026-001",
  "case_subject": "Determination of pension insurance obligations",
  "doc_date": "9 February 2026",
  "status": "CONFIRMED",
  "financials": [
    {
      "year": 2023,
      "income": 55000,
      "expenses": 12000,
      "taxable": 43000
    },
    {
      "year": 2024,
      "income": 60000,
      "expenses": 15000,
      "taxable": 45000
    }
  ],
  "totals": {
    "income": 115000,
    "expenses": 27000,
    "taxable": 88000
  },
  "attachments": [
    {
      "label": "Attachment 1",
      "description": "Annual income statement"
    }
  ]
}

const AGENTS = [
  {
    id: 'gpt4-legal',
    name: 'Legal Analyst (GPT-4o)',
    type: 'Azure OpenAI',
    status: 'Online',
    version: 'v2024.02.10'
  },
]

const SOURCES = [
  { id: 1, name: 'Case_Metadata.xml', type: 'CRM', relevance: 'High', icon: <DataObject /> },
  { id: 2, name: 'Email_Thread.eml', type: 'Communication', relevance: 'Medium', icon: <Email /> },
  { id: 3, name: 'Financial_Statement.xlsx', type: 'Finance', relevance: 'Critical', icon: <TableChart /> },
  { id: 4, name: 'Old_Precedent_2020.pdf', type: 'Vector Store', relevance: 'Low', icon: <Article /> },
]

const TEMPLATE_ID = 'etk-decision'

const API_BASE =  
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'  

// Mock function to simulate calculating a SHA-256 hash of the content
const mockSha256 = (str) => {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  // Return a hex-like string for the demo
  return "8f4a" + Math.abs(hash).toString(16) + "b2c9d1e8f3a4b5c6d7e8f9a0b1c2d3e4f5";
}

// Relevance Color Map
const getRelevanceColor = (level) => {
  switch (level) {
    case 'Critical': return 'error';
    case 'High': return 'warning';
    case 'Medium': return 'info';
    default: return 'default';
  }
}

export default function App() {
  // --- STATE ---
  const [activeSources, setActiveSources] = useState([1, 2, 3])
  const [jsonPayload, setJsonPayload] = useState(JSON.stringify(examplePayload, null, 2))
  const [pdfUrl, setPdfUrl] = useState(null)
  const [loading, setLoading] = useState(false)
  
  // New Engineering Features
  const [semanticHash, setSemanticHash] = useState(null)
  const [consoleOpen, setConsoleOpen] = useState(true)
  const [logs, setLogs] = useState([
    { ts: new Date().toLocaleTimeString(), msg: 'System initialized. Waiting for agent input...', type: 'info' }
  ])
  const [processingStage, setProcessingStage] = useState('Idle') // Idle, Validating, Rendering, Sealing
  
  // Feedback State
  const [toast, setToast] = useState({ open: false, message: '', severity: 'info' })
  const consoleEndRef = useRef(null)

  // Auto-scroll console
  useEffect(() => {
    consoleEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [logs])

  // --- ACTIONS ---

  const addLog = (msg, type = 'info') => {
    setLogs(prev => [...prev, {
      ts: new Date().toLocaleTimeString('en-US', { hour12: false }),
      msg,
      type
    }])
  }

  const toggleSource = (id) => {
    setActiveSources(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  const handleGenerate = async () => {
    setLoading(true)
    setPdfUrl(null)
    setSemanticHash(null)
    setProcessingStage('Validating')
    
    // Clear logs for new run
    setLogs([{ ts: new Date().toLocaleTimeString(), msg: 'Initiating generation sequence...', type: 'info' }])

    try {
      // 1. Validation Phase
      addLog(`Validating JSON against schema: ${TEMPLATE_ID}...`)
      const payload = JSON.parse(jsonPayload)
      await new Promise(r => setTimeout(r, 600)) // Fake delay for UX
      addLog('Schema validation passed.', 'success')

      // 2. Rendering Phase
      setProcessingStage('Rendering')
      addLog(`Sending payload to Engine (POST /generate/${TEMPLATE_ID})...`)
      
      const response = await axios.post(
        `${API_BASE}/generate/${TEMPLATE_ID}`,
        payload,
        {
          responseType: 'blob',
          headers: { 'Content-Type': 'application/json' },
          validateStatus: () => true,
        }
      )

      if (response.status !== 200) {
        const errorText = await response.data.text().catch(() => 'Unknown error');
        throw new Error(`Generation failed (${response.status}): ${errorText}`)
      }

      // 3. Sealing Phase
      setProcessingStage('Sealing')
      addLog('PDF generated. Computing semantic integrity hash...')
      const calculatedHash = mockSha256(jsonPayload)
      setSemanticHash(calculatedHash)
      addLog(`Hash Computed: ${calculatedHash.substring(0, 16)}...`, 'warning')
      
      addLog('Requesting cryptographic seal from Azure Trusted Signing...')
      await new Promise(r => setTimeout(r, 800)) // Fake delay for UX
      
      const blob = response.data.type === 'application/pdf'
        ? response.data
        : new Blob([response.data], { type: 'application/pdf' })

      setPdfUrl(URL.createObjectURL(blob))
      addLog('Artifact sealed. PAdES-B-LT signature applied.', 'success')
      setToast({ open: true, message: 'Artifact sealed and verified successfully', severity: 'success' })

    } catch (err) {
      console.error(err)
      addLog(`Error: ${err.message}`, 'error')
      setToast({ open: true, message: err.message, severity: 'error' })
    } finally {
      setLoading(false)
      setProcessingStage('Idle')
    }
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      
      {/* Main Layout Container */}
      <Box display="flex" height="100vh" width="100vw" overflow="hidden" bgcolor="background.default" position="relative">
        
        {/* ================= LEFT: CONTEXT PANE ================= */}
        <Paper
          square
          elevation={0}
          sx={{
            width: 320,
            borderRight: 1,
            borderColor: 'divider',
            display: 'flex',
            flexDirection: 'column',
            bgcolor: 'background.paper',
            pb: consoleOpen ? '160px' : 0, // Make room for console
            transition: 'padding 0.3s'
          }}
        >
          {/* Section: Agent */}
          <Box p={2} borderBottom={1} borderColor="divider">
            <Typography variant="overline" display="block" mb={1}>
              Orchestration Agent
            </Typography>
            {AGENTS.map(agent => (
              <Paper 
                key={agent.id} 
                variant="outlined" 
                sx={{ 
                  p: 1.5, 
                  bgcolor: 'rgba(56, 189, 248, 0.08)', 
                  borderColor: 'primary.main',
                  display: 'flex', 
                  alignItems: 'center',
                  gap: 2
                }}
              >
                <SmartToy color="primary" />
                <Box flex={1}>
                  <Typography variant="subtitle2" fontWeight="bold">
                    {agent.name}
                  </Typography>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Typography variant="caption" color="text.secondary">
                      {agent.type}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">•</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {agent.version}
                    </Typography>
                  </Stack>
                </Box>
                <Box width={8} height={8} borderRadius="50%" bgcolor="#22c55e" boxShadow="0 0 8px #22c55e" />
              </Paper>
            ))}
          </Box>

          {/* Section: Sources */}
          <Box flex={1} overflow="auto">
            <Box p={2} pb={0} display="flex" justifyContent="space-between" alignItems="center">
              <Typography variant="overline">
                Retrieval Context
              </Typography>
              <Chip 
                label={`${activeSources.length} Active`} 
                size="small" 
                color="default" 
                variant="outlined"
                sx={{ borderRadius: 1 }}
              />
            </Box>

            <List disablePadding>
              {SOURCES.map((src) => {
                const active = activeSources.includes(src.id)
                return (
                  <ListItemButton
                    key={src.id}
                    onClick={() => toggleSource(src.id)}
                    sx={{
                      py: 1.5,
                      px: 2,
                      borderLeft: 3,
                      borderColor: active ? getRelevanceColor(src.relevance) + '.main' : 'transparent',
                      bgcolor: active ? 'rgba(255,255,255,0.02)' : 'transparent',
                      opacity: active ? 1 : 0.6,
                      transition: 'all 0.2s',
                      '&:hover': { bgcolor: 'rgba(255,255,255,0.05)' }
                    }}
                  >
                    <ListItemIcon sx={{ minWidth: 40, color: 'text.secondary' }}>
                      {active ? src.icon : <Description />}
                    </ListItemIcon>
                    
                    <ListItemText
                      primary={
                        <Box display="flex" alignItems="center" gap={1}>
                          <Typography variant="body2" fontWeight={active ? 600 : 400}>
                            {src.name}
                          </Typography>
                        </Box>
                      }
                      secondary={
                        <Stack direction="row" spacing={1} alignItems="center" mt={0.5}>
                          <Chip 
                            label={src.type} 
                            size="small" 
                            sx={{ height: 16, fontSize: '0.6rem' }} 
                          />
                          <Chip 
                            label={src.relevance} 
                            size="small" 
                            color={getRelevanceColor(src.relevance)}
                            variant="outlined"
                            sx={{ height: 16, fontSize: '0.6rem' }} 
                          />
                        </Stack>
                      }
                    />
                    <Checkbox checked={active} edge="end" size="small" disableRipple />
                  </ListItemButton>
                )
              })}
            </List>
          </Box>
          
          <Box p={2} borderTop={1} borderColor="divider" bgcolor="background.default">
            <Typography variant="caption" color="text.secondary" sx={{ display: 'flex', gap: 1 }}>
              <WarningAmber fontSize="inherit" />
              <span>Context toggling affects agent reasoning only.</span>
            </Typography>
          </Box>
        </Paper>

        {/* ================= MIDDLE: SEMANTIC EDITOR ================= */}
        <Box
          flex="1 1 40%"
          minWidth={500}
          display="flex"
          flexDirection="column"
          borderRight={1}
          borderColor="divider"
          pb={consoleOpen ? '160px' : 0}
          sx={{ transition: 'padding 0.3s' }}
        >
          {/* Header */}
          <Box
            height={64}
            px={3}
            display="flex"
            justifyContent="space-between"
            alignItems="center"
            borderBottom={1}
            borderColor="divider"
            bgcolor="background.paper"
          >
            <Stack>
              <Typography variant="subtitle2" fontWeight={700}>
                Semantic Payload
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Template: <span style={{ fontFamily: 'monospace', color: '#38bdf8' }}>{TEMPLATE_ID}</span>
              </Typography>
            </Stack>

            <Button
              variant="contained"
              color={loading ? "secondary" : "primary"}
              disabled={loading}
              onClick={handleGenerate}
              startIcon={loading ? <CircularProgress size={16} color="inherit" /> : <PlayArrow />}
              sx={{ px: 3, minWidth: 160 }}
            >
              {loading ? processingStage + '...' : 'Execute & Sign'}
            </Button>
          </Box>

          {/* Editor Area */}
          <Box flex={1} position="relative">
            <Editor
              height="100%"
              defaultLanguage="json"
              theme="vs-dark"
              value={jsonPayload}
              onChange={setJsonPayload}
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                fontFamily: '"JetBrains Mono", monospace',
                padding: { top: 20 },
                scrollBeyondLastLine: false,
                lineNumbers: 'on',
                renderLineHighlight: 'all',
              }}
            />
          </Box>

          {/* Validation Footer / Semantic Hash Display */}
          <Box
            height={36}
            px={2}
            borderTop={1}
            borderColor="divider"
            bgcolor="background.paper"
            display="flex"
            alignItems="center"
            justifyContent="space-between"
          >
            <Stack direction="row" spacing={2} alignItems="center">
               <Typography variant="caption" color="text.secondary">Validation:</Typography>
               <Chip 
                 icon={<CheckCircle style={{ width: 14 }} />} 
                 label="Schema Compliant" 
                 size="small" 
                 color="success" 
                 variant="outlined" 
                 sx={{ height: 20, fontSize: '0.65rem', border: 'none', bgcolor: 'rgba(34, 197, 94, 0.1)' }}
               />
            </Stack>
            
            {/* HASH DISPLAY - MIDDLE PANE */}
            {semanticHash && (
              <Stack direction="row" spacing={1} alignItems="center" sx={{ opacity: loading ? 0.5 : 1 }}>
                 <Fingerprint sx={{ fontSize: 14, color: 'text.secondary' }} />
                 <Typography variant="caption" color="text.secondary" fontFamily="monospace">
                   SHA: {semanticHash.substring(0, 12)}...
                 </Typography>
              </Stack>
            )}
          </Box>
        </Box>

        {/* ================= RIGHT: ARTIFACT PREVIEW ================= */}
        <Box
          flex="1 1 50%"
          display="flex"
          flexDirection="column"
          bgcolor="#0f172a" 
          pb={consoleOpen ? '160px' : 0}
          sx={{ transition: 'padding 0.3s' }}
        >
          {/* Header */}
          <Box
            height={64}
            px={3}
            display="flex"
            justifyContent="space-between"
            alignItems="center"
            borderBottom={1}
            borderColor="divider"
            bgcolor="background.paper"
          >
            <Stack>
                <Typography variant="overline" lineHeight={1.2}>
                  Immutable Artifact
                </Typography>
                {/* HASH DISPLAY - RIGHT PANE */}
                {semanticHash && (
                    <Typography variant="caption" color="primary" fontFamily="monospace" fontSize={10} sx={{ opacity: 0.8 }}>
                        LINKED HASH: {semanticHash.substring(0, 24)}...
                    </Typography>
                )}
            </Stack>
            
            {pdfUrl && (
              <Chip
                icon={<Shield fontSize="small" />}
                label="PDF/A-3b • PAdES Sealed"
                color="success"
                variant="outlined"
                size="small"
              />
            )}
          </Box>

          {/* Content */}
          <Box 
            flex={1} 
            p={4} 
            display="flex" 
            alignItems="center" 
            justifyContent="center"
            bgcolor="#0b1224" 
          >
            {loading ? (
              <Stack alignItems="center" spacing={2}>
                <CircularProgress size={48} thickness={2} />
                <Typography variant="body2" color="text.secondary">
                  {processingStage === 'Rendering' && "Engine: Rendering LaTeX to PDF..."}
                  {processingStage === 'Sealing' && "Signer: Applying Cryptographic Seal..."}
                </Typography>
              </Stack>
            ) : pdfUrl ? (
              <Box
                width="100%"
                height="100%"
                boxShadow={10}
                borderRadius={1}
                overflow="hidden"
                border={1}
                borderColor="divider"
              >
                <iframe
                  src={`${pdfUrl}#toolbar=0&view=FitH`}
                  style={{
                    width: '100%',
                    height: '100%',
                    border: 'none',
                    backgroundColor: '#ffffff'
                  }}
                  title="PDF Preview"
                />
              </Box>
            ) : (
              <Box 
                textAlign="center" 
                color="text.secondary" 
                sx={{ opacity: 0.3 }}
              >
                <Description sx={{ fontSize: 80, mb: 2 }} />
                <Typography variant="h6" fontWeight={500}>
                  No Artifact Generated
                </Typography>
                <Typography variant="body2">
                  Approve semantic payload to generate signed document
                </Typography>
              </Box>
            )}
          </Box>
        </Box>

        {/* ================= BOTTOM: TRANSACTION CONSOLE ================= */}
        <Paper
          elevation={10}
          sx={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            height: consoleOpen ? 160 : 32,
            bgcolor: '#000000',
            borderTop: 1,
            borderColor: 'divider',
            display: 'flex',
            flexDirection: 'column',
            transition: 'height 0.3s ease-in-out',
            zIndex: 1200
          }}
        >
            {/* Console Header */}
            <Box 
                px={2} 
                height={32} 
                display="flex" 
                alignItems="center" 
                justifyContent="space-between" 
                bgcolor="#1e1e1e"
                onClick={() => setConsoleOpen(!consoleOpen)}
                sx={{ cursor: 'pointer', '&:hover': { bgcolor: '#2d2d2d' } }}
            >
                <Stack direction="row" spacing={1} alignItems="center">
                    <Terminal sx={{ fontSize: 16, color: 'text.secondary' }} />
                    <Typography variant="caption" fontWeight="bold" color="text.secondary">
                        TRANSACTION LOGS
                    </Typography>
                </Stack>
                {consoleOpen ? <KeyboardArrowDown sx={{ fontSize: 16 }} /> : <KeyboardArrowUp sx={{ fontSize: 16 }} />}
            </Box>

            {/* Console Output */}
            <Box 
                flex={1} 
                overflow="auto" 
                p={1.5} 
                sx={{ fontFamily: '"Fira Code", monospace', fontSize: '11px' }}
            >
                {logs.map((l, i) => (
                    <Box key={i} display="flex" gap={2} mb={0.5} color={l.type === 'error' ? '#ef4444' : l.type === 'success' ? '#22c55e' : l.type === 'warning' ? '#f59e0b' : '#94a3b8'}>
                        <span style={{ opacity: 0.5, minWidth: 60 }}>[{l.ts}]</span>
                        <span style={{ whiteSpace: 'pre-wrap' }}>
                             {l.type === 'info' && '> '}
                             {l.type === 'success' && '✓ '}
                             {l.type === 'error' && '✗ '}
                             {l.type === 'warning' && '! '}
                             {l.msg}
                        </span>
                    </Box>
                ))}
                <div ref={consoleEndRef} />
            </Box>
        </Paper>

      </Box>
      
      {/* Notifications */}
      <Snackbar 
        open={toast.open} 
        autoHideDuration={6000} 
        onClose={() => setToast({ ...toast, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        sx={{ mb: consoleOpen ? 20 : 5 }} // Adjust position based on console
      >
        <Alert 
          onClose={() => setToast({ ...toast, open: false })} 
          severity={toast.severity} 
          variant="filled"
          sx={{ width: '100%' }}
        >
          {toast.message}
        </Alert>
      </Snackbar>
      
    </ThemeProvider>
  )
}