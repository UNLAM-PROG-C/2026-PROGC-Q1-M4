const canvas = document.getElementById(ID_PARTICLES);
const ctx = canvas.getContext("2d");
let W,
  H,
  particles = [],
  animFrame;
let mode = MODE_IDLE;

const COLORS = ["#a78bfa", "#34d399", "#60a5fa", "#f472b6", "#fbbf24"];

// ── Particle animation tuning ─────────────────────────────────────────────
const IDLE_PARTICLE_COUNT = 60;
const LOADING_PARTICLE_COUNT = 160;
const DONE_PARTICLE_COUNT = 90;

const FAST_SPEED = 2.5;
const SLOW_SPEED = 0.8;
const FAST_RADIUS = 3.5;
const SLOW_RADIUS = 2.5;
const MIN_RADIUS = 0.5;
const ALPHA_RANGE = 0.6;
const MIN_ALPHA = 0.1;
const MIN_MAX_LIFE = 200;
const MAX_LIFE_RANGE = 300;
const CENTER_OFFSET = 0.5;
const FULL_TURN = Math.PI * 2;

const PULSE_STEP = 0.04;
const JITTER = 0.1;
const MAX_SPEED = 3;
const FADE_IN_THRESHOLD = 0.1;
const FADE_OUT_THRESHOLD = 0.9;
const FADE_MULTIPLIER = 10;
const FULL_OPACITY = 1;
const PULSE_AMPLITUDE = 0.3;
const BYTE_MAX = 255;
const HEX_RADIX = 16;
const HEX_PADDING = 2;
const TRAIL_LENGTH = 4;
const TRAIL_WIDTH_FACTOR = 0.5;
const TRAIL_ALPHA_HEX = "44";
const LINK_DISTANCE = 80;
const LINK_ALPHA_SCALE = 40;
const LINK_WIDTH = 0.5;

function resize() {
  W = canvas.width = window.innerWidth;
  H = canvas.height = window.innerHeight;
}
resize();
window.addEventListener(EVENT_RESIZE, resize);

function toHexByte(value) {
  return Math.floor(value).toString(HEX_RADIX).padStart(HEX_PADDING, "0");
}

function Particle(fast) {
  this.reset = function (fast) {
    this.x = Math.random() * W;
    this.y = Math.random() * H;
    this.vx =
      (Math.random() - CENTER_OFFSET) * (fast ? FAST_SPEED : SLOW_SPEED);
    this.vy =
      (Math.random() - CENTER_OFFSET) * (fast ? FAST_SPEED : SLOW_SPEED);
    this.r = Math.random() * (fast ? FAST_RADIUS : SLOW_RADIUS) + MIN_RADIUS;
    this.alpha = Math.random() * ALPHA_RANGE + MIN_ALPHA;
    this.color = COLORS[Math.floor(Math.random() * COLORS.length)];
    this.life = 0;
    this.maxLife = MIN_MAX_LIFE + Math.random() * MAX_LIFE_RANGE;
    this.pulse = Math.random() * FULL_TURN;
    this.trail = [];
  };
  this.reset(fast);
}

function initParticles(count) {
  particles = [];
  for (let i = 0; i < count; i++)
    particles.push(new Particle(mode === MODE_LOADING));
}

function setMode(m) {
  mode = m;
  cancelAnimationFrame(animFrame);
  if (m === MODE_IDLE) initParticles(IDLE_PARTICLE_COUNT);
  if (m === MODE_LOADING) initParticles(LOADING_PARTICLE_COUNT);
  if (m === MODE_DONE) initParticles(DONE_PARTICLE_COUNT);
  draw();
}

function applyTurbulence(p) {
  p.vx += (Math.random() - CENTER_OFFSET) * JITTER;
  p.vy += (Math.random() - CENTER_OFFSET) * JITTER;
  const speed = Math.sqrt(p.vx * p.vx + p.vy * p.vy);
  if (speed > MAX_SPEED) {
    p.vx *= MAX_SPEED / speed;
    p.vy *= MAX_SPEED / speed;
  }
}

function wrapAround(p) {
  if (p.x < 0) p.x = W;
  if (p.x > W) p.x = 0;
  if (p.y < 0) p.y = H;
  if (p.y > H) p.y = 0;
}

function computeFadeAlpha(lifeRatio) {
  if (lifeRatio < FADE_IN_THRESHOLD) return lifeRatio * FADE_MULTIPLIER;
  if (lifeRatio > FADE_OUT_THRESHOLD) return (1 - lifeRatio) * FADE_MULTIPLIER;
  return FULL_OPACITY;
}

function drawParticleBody(p, radius, fadeAlpha) {
  ctx.beginPath();
  ctx.arc(p.x, p.y, radius, 0, FULL_TURN);
  ctx.fillStyle = p.color + toHexByte(p.alpha * fadeAlpha * BYTE_MAX);
  ctx.fill();
}

function drawParticleTrail(p, radius) {
  ctx.beginPath();
  ctx.moveTo(p.x, p.y);
  ctx.lineTo(p.x - p.vx * TRAIL_LENGTH, p.y - p.vy * TRAIL_LENGTH);
  ctx.strokeStyle = p.color + TRAIL_ALPHA_HEX;
  ctx.lineWidth = radius * TRAIL_WIDTH_FACTOR;
  ctx.stroke();
}

function updateParticle(p, fast, done) {
  p.pulse += PULSE_STEP;
  p.life++;
  p.x += p.vx;
  p.y += p.vy;

  if (fast) applyTurbulence(p);
  wrapAround(p);
  if (p.life > p.maxLife) p.reset(fast);

  const fadeAlpha = computeFadeAlpha(p.life / p.maxLife);
  const radius = p.r * (1 + PULSE_AMPLITUDE * Math.sin(p.pulse));
  drawParticleBody(p, radius, fadeAlpha);
  if (fast || done) drawParticleTrail(p, radius);
}

function drawLink(a, b, dist) {
  ctx.beginPath();
  ctx.moveTo(a.x, a.y);
  ctx.lineTo(b.x, b.y);
  ctx.strokeStyle =
    a.color + toHexByte((1 - dist / LINK_DISTANCE) * LINK_ALPHA_SCALE);
  ctx.lineWidth = LINK_WIDTH;
  ctx.stroke();
}

function drawLinks() {
  for (let i = 0; i < particles.length; i++) {
    for (let j = i + 1; j < particles.length; j++) {
      const a = particles[i];
      const b = particles[j];
      const dx = a.x - b.x;
      const dy = a.y - b.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < LINK_DISTANCE) drawLink(a, b, dist);
    }
  }
}

function draw() {
  ctx.clearRect(0, 0, W, H);
  const fast = mode === MODE_LOADING;
  const done = mode === MODE_DONE;

  particles.forEach((p) => updateParticle(p, fast, done));
  if (fast) drawLinks();

  animFrame = requestAnimationFrame(draw);
}

setMode(MODE_IDLE);
