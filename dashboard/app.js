const lanesRoot = document.querySelector('#laneCards');
const totalVehicles = document.querySelector('#totalVehicles');
const busiest = document.querySelector('#busiest');
const modelStatus = document.querySelector('#modelStatus');
const modelMessage = document.querySelector('#modelMessage');
const sourceStatus = document.querySelector('#sourceStatus');
const placeholder = document.querySelector('#placeholder');
const updatedAt = document.querySelector('#updatedAt');
const connection = document.querySelector('#connection');
const signals = {
  A: {
    red: document.querySelector('#signalARed'),
    yellow: document.querySelector('#signalAYellow'),
    green: document.querySelector('#signalAGreen'),
    status: document.querySelector('#signalAStatus'),
    countdown: document.querySelector('#signalACountdown'),
  },
  B: {
    red: document.querySelector('#signalBRed'),
    yellow: document.querySelector('#signalBYellow'),
    green: document.querySelector('#signalBGreen'),
    status: document.querySelector('#signalBStatus'),
    countdown: document.querySelector('#signalBCountdown'),
  },
};
let latestState = null;
const signalEpoch = Date.now();

function render(state) {
  latestState = state;
  const lanes = state.lanes || [];
  const total = lanes.reduce((sum, lane) => sum + lane.vehicles, 0);
  const maxCount = Math.max(1, ...lanes.map(lane => lane.vehicles));
  totalVehicles.textContent = String(total).padStart(2, '0');
  const topLane = [...lanes].sort((a, b) => b.vehicles - a.vehicles)[0];
  busiest.textContent = topLane ? topLane.name : '—';
  modelStatus.textContent = state.model_ready ? 'Ready' : 'Not loaded';
  modelMessage.textContent = state.model_message || 'YOLOv8 vehicle model';
  sourceStatus.textContent = (state.status || 'waiting').toUpperCase();
  placeholder.style.display = state.updated_at ? 'none' : 'flex';
  updatedAt.textContent = state.updated_at ? `Updated ${new Date(state.updated_at * 1000).toLocaleTimeString()}` : 'No frames yet';
  lanesRoot.replaceChildren(...lanes.map(lane => {
    const card = document.createElement('article');
    card.className = 'lane-card';
    const head = document.createElement('div');
    head.className = 'lane-head';
    const name = document.createElement('span');
    name.className = 'lane-name';
    name.textContent = lane.name;
    const count = document.createElement('span');
    count.className = 'lane-count';
    count.textContent = `${lane.vehicles} VEHICLES`;
    head.append(name, count);
    const meta = document.createElement('div');
    meta.className = 'lane-meta';
    const time = document.createElement('strong');
    time.textContent = `${lane.green_seconds}s`;
    const caption = document.createElement('small');
    caption.textContent = 'estimated green time';
    meta.append(time, caption);
    const track = document.createElement('div');
    track.className = 'bar-track';
    const fill = document.createElement('div');
    fill.className = 'bar-fill';
    fill.style.width = `${Math.round(lane.vehicles / maxCount * 100)}%`;
    track.append(fill);
    card.append(head, meta, track);
    return card;
  }));
  updateSignal();
}

function updateSignal() {
  const lanes = latestState?.lanes || [];
  if (lanes.length < 2) return;
  const amberSeconds = 3;
  const clearanceSeconds = 2;
  const firstGreen = Math.max(10, Number(lanes[0].green_seconds) || 30);
  const secondGreen = Math.max(10, Number(lanes[1].green_seconds) || 30);
  const phases = [
    { a: 'green', b: 'red', duration: firstGreen },
    { a: 'yellow', b: 'red', duration: amberSeconds },
    { a: 'red', b: 'red', duration: clearanceSeconds },
    { a: 'red', b: 'green', duration: secondGreen },
    { a: 'red', b: 'yellow', duration: amberSeconds },
    { a: 'red', b: 'red', duration: clearanceSeconds },
  ];
  const cycleLength = phases.reduce((sum, phase) => sum + phase.duration, 0);
  const position = ((Date.now() - signalEpoch) / 1000) % cycleLength;
  let phaseIndex = 0;
  let phaseOffset = position;
  while (phaseOffset >= phases[phaseIndex].duration) {
    phaseOffset -= phases[phaseIndex].duration;
    phaseIndex = (phaseIndex + 1) % phases.length;
  }
  const phase = phases[phaseIndex];
  const phaseRemaining = phase.duration - phaseOffset;
  let aNextGreen = phaseRemaining;
  let bNextGreen = phaseRemaining;
  if (phaseIndex === 0) bNextGreen += amberSeconds + clearanceSeconds;
  if (phaseIndex === 1) bNextGreen += clearanceSeconds;
  if (phaseIndex === 2) bNextGreen += firstGreen + amberSeconds + clearanceSeconds;
  if (phaseIndex === 3) aNextGreen += amberSeconds + clearanceSeconds;
  if (phaseIndex === 4) aNextGreen += clearanceSeconds;
  if (phaseIndex === 5) bNextGreen += firstGreen + amberSeconds + clearanceSeconds;
  updateSignalUnit(signals.A, phase.a, phaseRemaining, aNextGreen);
  updateSignalUnit(signals.B, phase.b, phaseRemaining, bNextGreen);
}

function updateSignalUnit(signal, color, phaseRemaining, nextGreen) {
  signal.red.classList.toggle('active', color === 'red');
  signal.yellow.classList.toggle('active', color === 'yellow');
  signal.green.classList.toggle('active', color === 'green');
  signal.status.textContent = color.toUpperCase();
  signal.status.className = `signal-state ${color}`;
  const seconds = color === 'red' ? nextGreen : phaseRemaining;
  signal.countdown.textContent = color === 'red'
    ? `${Math.max(1, Math.ceil(seconds))} sec to green`
    : `${Math.max(1, Math.ceil(seconds))} sec remaining`;
}

function connect() {
  const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(`${scheme}//${location.host}/ws`);
  socket.onopen = () => { connection.textContent = 'CONNECTED'; };
  socket.onmessage = event => render(JSON.parse(event.data));
  socket.onclose = () => {
    connection.textContent = 'RECONNECTING';
    setTimeout(connect, 2000);
  };
  socket.onerror = () => socket.close();
}

const uploadForm = document.querySelector('#videoUpload');
const uploadButton = document.querySelector('#uploadButton');
const uploadMessage = document.querySelector('#uploadMessage');

uploadForm.addEventListener('submit', async event => {
  event.preventDefault();
  const input = document.querySelector('#videoFile');
  if (!input.files.length) return;

  uploadButton.disabled = true;
  uploadButton.textContent = 'Uploading...';
  uploadMessage.textContent = `Preparing ${input.files[0].name}`;

  const formData = new FormData();
  formData.append('file', input.files[0]);
  try {
    const response = await fetch('/api/upload-video', { method: 'POST', body: formData });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || 'Upload failed');
    uploadMessage.textContent = `Now analyzing ${result.filename}`;
  } catch (error) {
    uploadMessage.textContent = error.message;
  } finally {
    uploadButton.disabled = false;
    uploadButton.textContent = 'Use video';
  }
});

fetch('/api/status').then(response => response.json()).then(render).catch(() => {});
connect();
setInterval(updateSignal, 500);
