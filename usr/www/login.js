const loginForm = document.getElementById('login_form')
const loginUser = document.getElementById('login_user')
const loginPass = document.getElementById('login_pass')
const passwordToggle = document.getElementById('password_toggle')
const loginError = document.getElementById('login_error')
const loginSubmit = document.getElementById('login_submit')

const showError = message => {
  if (!loginError) return
  loginError.textContent = message
  loginError.hidden = !message
}

const checkExistingSession = async () => {
  try {
    const response = await fetch('/command/auth-check', { credentials: 'include' })
    if (response.ok) {
      window.location.replace('/')
    }
  } catch (err) {
    // Sin sesion activa
  }
}

const submitLogin = async event => {
  event.preventDefault()
  showError('')

  if (loginSubmit) loginSubmit.disabled = true

  try {
    const response = await fetch('/command/login', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user: loginUser ? loginUser.value.trim() : '',
        pass: loginPass ? loginPass.value : '',
      }),
    })

    const data = await response.json().catch(() => ({}))
    if (!response.ok || data.status !== 'success') {
      if (data.message) {
        showError(data.message)
      } else if (response.status >= 500) {
        showError('Error interno del servidor')
      } else {
        showError('Usuario o contrasena incorrectos')
      }
      return
    }

    window.location.replace('/')
  } catch (err) {
    showError('No se pudo conectar con el modem')
  } finally {
    if (loginSubmit) loginSubmit.disabled = false
  }
}

if (loginForm) {
  loginForm.addEventListener('submit', submitLogin)
}

if (passwordToggle && loginPass) {
  passwordToggle.addEventListener('click', () => {
    const show = loginPass.type === 'password'
    loginPass.type = show ? 'text' : 'password'
    passwordToggle.textContent = show ? 'Ocultar' : 'Mostrar'
    passwordToggle.setAttribute('aria-label', show ? 'Ocultar contrasena' : 'Mostrar contrasena')
  })
}

window.addEventListener('load', checkExistingSession)
