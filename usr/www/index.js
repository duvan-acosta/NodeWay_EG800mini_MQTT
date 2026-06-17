const IMEI = document.getElementById('imei')
const Serial = document.getElementById('serial')
const Firmware = document.getElementById('firmware')
const Operador = document.getElementById('operador')
const IP_SIM = document.getElementById('ipsim')
const NetMode = document.getElementById('netmode')
const RSSI = document.getElementById('rssi')
const RSRP = document.getElementById('rsrp')
const RSRQ = document.getElementById('rsrq')
const CQI = document.getElementById('cqi')

const bootreason = document.getElementById('bootreason')
const shutdownreason = document.getElementById('shutdownreason')
const estadosupercondensador = document.getElementById('estadosupercondensador')
const uptimeEl = document.getElementById('uptime')

const RS485Puerto = document.getElementById('puerto485')
const RS485Vel = document.getElementById('baudratec485')
const RS485DataBit = document.getElementById('databits485')
const RS485Paridad = document.getElementById('parity485')
const RS485StopBit = document.getElementById('stopbits485')
const RS485Timeout = document.getElementById('timeout485')

const APNCid = document.getElementById('apn_cid')
const APNPdp = document.getElementById('apn_pdp')
const APNName = document.getElementById('apn_name')
const APNUser = document.getElementById('apn_user')
const APNPass = document.getElementById('apn_pass')
const APNAuth = document.getElementById('apn_auth')
const NetModeSelect = document.getElementById('netmode_select')
const NetModeMsg = document.getElementById('netmode_msg')
const FotaForm = document.getElementById('fota_form')
const FotaStatus = document.getElementById('fota_status')
const FotaProgress = document.getElementById('fota_progress')
const RestartEnabled = document.getElementById('restart_enabled')
const RestartHours = document.getElementById('restart_hours')
const NetworkRecoveryEnabled = document.getElementById('network_recovery_enabled')
const StackRestartMin = document.getElementById('stack_restart_min')
const PowerRestartMin = document.getElementById('power_restart_min')
const NetworkRecoveryFields = document.getElementById('network_recovery_fields')
const RestartPolicyHint = document.getElementById('restart_policy_hint')
const RestartMsg = document.getElementById('restart_msg')
const MqttEnabled = document.getElementById('mqtt_enabled')
const MqttHost = document.getElementById('mqtt_host')
const MqttPort = document.getElementById('mqtt_port')
const MqttInterval = document.getElementById('mqtt_interval')
const MqttTopicPrefix = document.getElementById('mqtt_topic_prefix')
const MqttTopic = document.getElementById('mqtt_topic')
const MqttUser = document.getElementById('mqtt_user')
const MqttPass = document.getElementById('mqtt_pass')
const MqttMsg = document.getElementById('mqtt_msg')
const navStatusText = document.getElementById('nav_status_text')
const sidebarNav = document.getElementById('sidebar_nav')
const appShell = document.getElementById('app_shell')
const sidebarToggle = document.getElementById('sidebar_toggle')
const sidebarClose = document.getElementById('sidebar_close')
const sidebarBackdrop = document.getElementById('sidebar_backdrop')
const SIDEBAR_STORAGE_KEY = 'sidebar_collapsed'
const MOBILE_SIDEBAR_QUERY = window.matchMedia('(max-width: 900px)')

const isMobileSidebar = () => MOBILE_SIDEBAR_QUERY.matches

const setSidebarToggleState = expanded => {
  if (!sidebarToggle) return
  sidebarToggle.setAttribute('aria-expanded', expanded ? 'true' : 'false')
}

const applySidebarState = collapsed => {
  if (!appShell) return
  if (isMobileSidebar()) {
    appShell.classList.toggle('sidebar-open', !collapsed)
    appShell.classList.remove('sidebar-collapsed')
    if (sidebarBackdrop) sidebarBackdrop.hidden = collapsed
    setSidebarToggleState(!collapsed)
    return
  }
  appShell.classList.remove('sidebar-open')
  appShell.classList.toggle('sidebar-collapsed', collapsed)
  if (sidebarBackdrop) sidebarBackdrop.hidden = true
  setSidebarToggleState(!collapsed)
}

const getStoredSidebarCollapsed = () => {
  try {
    const stored = localStorage.getItem(SIDEBAR_STORAGE_KEY)
    if (stored === null) {
      return isMobileSidebar()
    }
    return stored === '1'
  } catch (err) {
    return isMobileSidebar()
  }
}

const storeSidebarCollapsed = collapsed => {
  try {
    localStorage.setItem(SIDEBAR_STORAGE_KEY, collapsed ? '1' : '0')
  } catch (err) {
    // ignore
  }
}

const toggleSidebar = () => {
  const collapsed = isMobileSidebar()
    ? appShell.classList.contains('sidebar-open')
    : !appShell.classList.contains('sidebar-collapsed')
  applySidebarState(collapsed)
  storeSidebarCollapsed(collapsed)
}

const initSidebarLayout = () => {
  if (!appShell) return
  const collapsed = getStoredSidebarCollapsed()
  applySidebarState(collapsed)

  if (sidebarToggle) {
    sidebarToggle.addEventListener('click', toggleSidebar)
  }
  if (sidebarClose) {
    sidebarClose.addEventListener('click', () => {
      applySidebarState(true)
      storeSidebarCollapsed(true)
    })
  }
  if (sidebarBackdrop) {
    sidebarBackdrop.addEventListener('click', () => {
      applySidebarState(true)
      storeSidebarCollapsed(true)
    })
  }

  const onViewportChange = () => {
    applySidebarState(getStoredSidebarCollapsed())
  }
  if (typeof MOBILE_SIDEBAR_QUERY.addEventListener === 'function') {
    MOBILE_SIDEBAR_QUERY.addEventListener('change', onViewportChange)
  } else if (typeof MOBILE_SIDEBAR_QUERY.addListener === 'function') {
    MOBILE_SIDEBAR_QUERY.addListener(onViewportChange)
  }
}

const getById = id => document.getElementById(id)

const formatUptime = seconds => {
  const total = Math.max(0, parseInt(seconds, 10) || 0)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  return (
    String(h).padStart(2, '0') +
    ':' +
    String(m).padStart(2, '0') +
    ':' +
    String(s).padStart(2, '0')
  )
}

const showPanel = panelId => {
  document.querySelectorAll('.panel').forEach(panel => {
    panel.classList.toggle('active', panel.id === panelId)
  })
  document.querySelectorAll('.sidebar-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.panel === panelId)
  })
  try {
    sessionStorage.setItem('active_panel', panelId)
  } catch (err) {
    // ignore
  }
  if (isMobileSidebar() && appShell && appShell.classList.contains('sidebar-open')) {
    applySidebarState(true)
    storeSidebarCollapsed(true)
  }
  if (panelId === 'panel-fota') {
    pollFotaStatus()
  }
}

const initSidebar = () => {
  if (!sidebarNav) return
  sidebarNav.querySelectorAll('.sidebar-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.dataset.panel) showPanel(btn.dataset.panel)
    })
  })
  let initialPanel = 'panel-modem'
  try {
    initialPanel = sessionStorage.getItem('active_panel') || initialPanel
  } catch (err) {
    // ignore
  }
  if (!document.getElementById(initialPanel)) {
    initialPanel = 'panel-modem'
  }
  showPanel(initialPanel)
}

const redirectToLogin = () => {
  window.location.href = '/login'
}

const API_TIMEOUT_MS = 30000

const apiFetch = async (url, options = {}) => {
  const { timeout = API_TIMEOUT_MS, ...fetchOptions } = options
  const controller = typeof AbortController !== 'undefined' ? new AbortController() : null
  let timeoutId = null
  if (controller && timeout > 0) {
    timeoutId = setTimeout(() => controller.abort(), timeout)
  }
  try {
    const response = await fetch(url, {
      ...fetchOptions,
      credentials: 'include',
      signal: controller ? controller.signal : undefined,
    })
    if (response.status === 401) {
      redirectToLogin()
      throw new Error('Unauthorized')
    }
    return response
  } catch (err) {
    if (err && err.name === 'AbortError') {
      throw new Error('Tiempo de espera agotado')
    }
    throw err
  } finally {
    if (timeoutId) clearTimeout(timeoutId)
  }
}

const ensureAuth = async () => {
  const response = await fetch('/command/auth-check', { credentials: 'include' })
  if (!response.ok) {
    redirectToLogin()
    return false
  }
  return true
}

const logout = async () => {
  try {
    await apiFetch('/command/logout', { method: 'POST' })
  } catch (err) {
    // Redirige igual si la sesion ya expiro
  } finally {
    redirectToLogin()
  }
}

const showSpinner = () => {
  const spinner = getById('spinner')
  if (spinner) spinner.style.display = 'flex'
}

const hideSpinner = () => {
  const spinner = getById('spinner')
  if (spinner) spinner.style.display = 'none'
}

const showModal = (title, body) => {
  const modal = getById('modal')
  const modalTitle = getById('modaltitle')
  const modalBody = getById('modalbody')
  if (modalTitle) modalTitle.textContent = title
  if (modalBody) modalBody.textContent = body
  if (modal) modal.style.display = 'flex'
}

const parseValue = value => {
  if (value === null || value === undefined) return null
  const num = parseFloat(value)
  return Number.isFinite(num) ? num : null
}

const netModeToText = mode => {
  if (mode === null || mode === undefined) return 'UNKNOWN'
  const act2g = [0, 1, 3]
  const act3g = [2, 4, 5, 6, 8]
  const act4g = [7, 9]
  if (act2g.includes(mode)) return '2G'
  if (act3g.includes(mode)) return '3G'
  if (act4g.includes(mode)) return '4G'
  if (mode === 0) return 'NO_SERVICE'
  if (mode === 1) return '2G'
  if (mode === 2) return '3G'
  if (mode === 3) return '4G'
  return 'UNKNOWN'
}

const updateNavStatus = (netTypeText, operatorName, ip) => {
  if (!navStatusText) return
  if (!ip || ip === '0.0.0.0' || netTypeText === 'UNKNOWN') {
    navStatusText.textContent = 'Sin red'
    return
  }
  const operatorPart = operatorName && operatorName !== 'N/A' ? operatorName : 'Operador'
  navStatusText.textContent = operatorPart + ' - ' + netTypeText
}

const applySignalBar = (barId, valueId, pct) => {
  const bar = getById(barId)
  const valueEl = getById(valueId)
  if (!bar || !valueEl) return

  const normalized = Math.max(0, Math.min(100, pct))
  bar.style.width = normalized + '%'

  if (normalized > 60) {
    bar.className = 'signal-bar signal-good'
    valueEl.style.color = 'var(--green)'
  } else if (normalized > 30) {
    bar.className = 'signal-bar signal-mid'
    valueEl.style.color = 'var(--yellow)'
  } else {
    bar.className = 'signal-bar signal-bad'
    valueEl.style.color = 'var(--red)'
  }
}

const updateSignalBars = () => {
  const rssi = parseValue(RSSI ? RSSI.textContent : null)
  const rsrp = parseValue(RSRP ? RSRP.textContent : null)
  const rsrq = parseValue(RSRQ ? RSRQ.textContent : null)
  const cqi = parseValue(CQI ? CQI.textContent : null)

  if (rssi !== null) {
    applySignalBar('rssi_bar', 'rssi', ((rssi + 110) / 60) * 100)
  } else {
    applySignalBar('rssi_bar', 'rssi', 0)
  }

  if (rsrp !== null) {
    applySignalBar('rsrp_bar', 'rsrp', ((rsrp + 140) / 60) * 100)
  } else {
    applySignalBar('rsrp_bar', 'rsrp', 0)
  }

  if (rsrq !== null) {
    applySignalBar('rsrq_bar', 'rsrq', ((rsrq + 20) / 17) * 100)
  } else {
    applySignalBar('rsrq_bar', 'rsrq', 0)
  }

  if (cqi !== null && cqi >= 0 && cqi <= 15) {
    applySignalBar('cqi_bar', 'cqi', (cqi / 15) * 100)
  } else {
    applySignalBar('cqi_bar', 'cqi', 0)
    if (CQI) CQI.style.color = 'var(--text2)'
  }
}

const getModemStatus = async () => {
  try {
    const response = await apiFetch('/command/getmodemstatus')
    if (!response.ok) {
      const text = await response.text()
      throw new Error('HTTP ' + response.status + ': ' + text)
    }

    const data = await response.json()
    if (data.status === 'error') {
      throw new Error(data.message || 'Error desconocido')
    }

    if (IMEI) IMEI.textContent = data.IMEI || 'N/A'
    if (Serial) Serial.textContent = data.Serial || 'N/A'
    if (Firmware) Firmware.textContent = data.Firmware || 'N/A'
    if (Operador) Operador.textContent = data.Operador || 'N/A'
    if (IP_SIM) IP_SIM.textContent = data.IP_SIM || '0.0.0.0'

    const netTypeText = data.NetModeText || netModeToText(data.NetMode)
    const modeCfg = parseInt(data.NetModeConfig)
    const autoModes = [2, 6, 9, 12, 16, 17, 18]
    if (NetMode) {
      NetMode.textContent = autoModes.includes(modeCfg)
        ? ['2G', '3G', '4G'].includes(netTypeText)
          ? 'AUTO (' + netTypeText + ')'
          : 'AUTO'
        : netTypeText
    }

    if (RSSI) RSSI.textContent = data.RSSI
    if (RSRP) RSRP.textContent = data.RSRP
    if (RSRQ) RSRQ.textContent = data.RSRQ
    if (CQI) CQI.textContent = data.CQI

    if (bootreason) bootreason.textContent = data.Motivo_Arranque || 'N/A'
    if (shutdownreason) shutdownreason.textContent = data.Motivo_Apagado || 'N/A'
    if (estadosupercondensador)
      estadosupercondensador.textContent = data.Estado_Supercondensador || 'N/A'
    if (uptimeEl) uptimeEl.textContent = formatUptime(data.UptimeSec)

    if (NetModeSelect) {
      let modeValue = null
      if (data.NetModeConfig !== undefined && data.NetModeConfig !== null) {
        modeValue = data.NetModeConfig.toString()
      }
      if (modeValue && ['12', '5', '1', '0'].includes(modeValue)) {
        NetModeSelect.value = modeValue
      }
    }

    updateNavStatus(netTypeText, data.Operador, data.IP_SIM)
    updateSignalBars()
  } catch (err) {
    console.log('Error getmodemstatus:', err)
    alert('Error al obtener el estado del modem')
  }
}

const getSerialDataConfig = async () => {
  const response = await apiFetch('/command/getconfig')
  const data = await response.json()

  if (RS485Puerto) RS485Puerto.value = String(data.RS485.Puerto)
  if (RS485Vel) RS485Vel.value = String(data.RS485.Vel)
  if (RS485DataBit) RS485DataBit.value = String(data.RS485.DataBit)
  if (RS485Paridad) RS485Paridad.value = String(data.RS485.Paridad)
  if (RS485StopBit) RS485StopBit.value = String(data.RS485.StopBit)
  if (RS485Timeout) RS485Timeout.value = String(data.RS485.Timeout)
}

const sanitizeApnField = value => {
  if (value === null || value === undefined) return ''
  const text = String(value)
  if (/[\u0000-\u001F\u007F\uFFFD]/.test(text)) return ''
  return text.trim()
}

const getApnConfig = async () => {
  const response = await apiFetch('/command/getapn')
  const data = await response.json()

  if (APNCid) APNCid.value = String(data.cid || 1)
  if (APNPdp) {
    const pdpValue = data.pdp_type_str || data.pdp_type || 'IP'
    APNPdp.value = String(pdpValue)
  }
  if (APNName) APNName.value = sanitizeApnField(data.apn)
  if (APNUser) APNUser.value = sanitizeApnField(data.user)
  if (APNPass) APNPass.value = sanitizeApnField(data.password)
  if (APNAuth) APNAuth.value = String(data.auth ?? 0)
}

const toggleNetworkRecoveryFields = () => {
  const enabled = NetworkRecoveryEnabled && NetworkRecoveryEnabled.value === '1'
  if (NetworkRecoveryFields) {
    NetworkRecoveryFields.style.display = enabled ? 'block' : 'none'
  }
}

const updateRestartPolicyHint = data => {
  if (!RestartPolicyHint) return
  const recovery = Boolean(data.NetworkRecoveryEnabled)
  const hours = data.IntervalHours || 12
  const stackMin = Math.round((data.StackRestartAfterNoNetworkSec || 0) / 60)
  const powerMin = Math.round((data.PowerRestartAfterNoNetworkSec || 0) / 60)
  const scheduled = data.Enabled
    ? 'Mantenimiento cada ' + hours + ' h.'
    : 'Sin reinicio programado.'
  if (recovery) {
    RestartPolicyHint.textContent =
      scheduled +
      ' Disponibilidad: recupera LTE a los ' +
      stackMin +
      ' min sin red y reinicia el modem a los ' +
      powerMin +
      ' min si no recupera conexion.'
  } else {
    RestartPolicyHint.textContent =
      scheduled + ' Recuperacion por fallo de red deshabilitada.'
  }
}

const getRestartConfig = async () => {
  const response = await apiFetch('/command/getrestart')
  const data = await response.json()
  if (RestartEnabled) RestartEnabled.value = data.Enabled ? '1' : '0'
  if (RestartHours) RestartHours.value = String(data.IntervalHours || 12)
  if (NetworkRecoveryEnabled) {
    NetworkRecoveryEnabled.value = data.NetworkRecoveryEnabled ? '1' : '0'
  }
  if (StackRestartMin) {
    StackRestartMin.value = String(
      Math.max(1, Math.round((data.StackRestartAfterNoNetworkSec || 300) / 60))
    )
  }
  if (PowerRestartMin) {
    PowerRestartMin.value = String(
      Math.max(5, Math.round((data.PowerRestartAfterNoNetworkSec || 900) / 60))
    )
  }
  toggleNetworkRecoveryFields()
  updateRestartPolicyHint(data)
}

const getMqttConfig = async () => {
  const response = await apiFetch('/command/getmqtt')
  const data = await response.json()
  if (MqttEnabled) MqttEnabled.value = data.Enabled ? '1' : '0'
  if (MqttHost) MqttHost.value = data.Host || ''
  if (MqttPort) MqttPort.value = String(data.Port || 1883)
  if (MqttInterval) {
    MqttInterval.value = String(Math.max(1, Math.round((data.IntervalSec || 300) / 60)))
  }
  if (MqttTopicPrefix) MqttTopicPrefix.value = data.TopicPrefix || 'MetaSense/ModemEGmini'
  if (MqttTopic) MqttTopic.value = data.Topic || ''
  if (MqttUser) MqttUser.value = data.User || ''
  if (MqttPass) MqttPass.value = data.Pass || ''
  if (MqttMsg) {
    MqttMsg.textContent = data.Enabled
      ? 'MQTT activo hacia ' + (data.Host || '-') + ':' + (data.Port || 1883)
      : 'MQTT deshabilitado.'
  }
}

const collectMqttFormData = () => ({
  Enabled: MqttEnabled && MqttEnabled.value === '1',
  Host: MqttHost ? MqttHost.value.trim() : '',
  Port: parseInt(MqttPort ? MqttPort.value : '1883', 10),
  IntervalSec: Math.max(1, parseInt(MqttInterval ? MqttInterval.value : '5', 10)) * 60,
  TopicPrefix: MqttTopicPrefix ? MqttTopicPrefix.value.trim() : '',
  User: MqttUser ? MqttUser.value.trim() : '',
  Pass: MqttPass ? MqttPass.value : '',
})

const setMqttConfig = async mqttData => {
  try {
    const response = await apiFetch('/command/setmqtt', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(mqttData),
    })
    const data = await response.json()

    if (data.status === 'success') {
      showModal('MQTT actualizado', 'La configuracion MQTT se guardo correctamente.')
      if (data.MQTT) {
        if (MqttTopic && data.MQTT.Topic) MqttTopic.value = data.MQTT.Topic
        if (MqttMsg) {
          MqttMsg.textContent = data.MQTT.Enabled
            ? 'MQTT activo hacia ' + data.MQTT.Host + ':' + data.MQTT.Port
            : 'MQTT deshabilitado.'
        }
      }
    } else {
      alert(data.message || 'Error al guardar MQTT')
    }
  } catch (err) {
    if (err && err.message !== 'Unauthorized') {
      alert('Error al guardar MQTT: ' + err.message)
    }
  } finally {
    hideSpinner()
  }
}

const setSerialDataConfig = async serialData => {
  try {
    const response = await apiFetch('/command/setconfig', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(serialData),
    })
    const data = await response.json()

    if (data.status === 'success') {
      showModal(
        'Configuracion guardada',
        'La configuracion se ha guardado correctamente. El modem se reiniciara para aplicar los cambios.'
      )
      setTimeout(() => {
        location.reload()
      }, 15000)
    } else {
      alert(data.message || 'Error al guardar la configuracion')
    }
  } catch (err) {
    if (err && err.message !== 'Unauthorized') {
      alert('Error al guardar la configuracion: ' + err.message)
    }
  } finally {
    hideSpinner()
  }
}

const setApnConfig = async apnData => {
  try {
    const response = await apiFetch('/command/setapn', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(apnData),
    })
    const data = await response.json()

    if (data.status === 'success') {
      showModal(
        'APN actualizado',
        'El APN se actualizo correctamente. Se reinicio la conexion de datos.'
      )
      setTimeout(() => {
        location.reload()
      }, 5000)
    } else {
      alert(data.message || 'Error al guardar el APN')
    }
  } catch (err) {
    if (err && err.message !== 'Unauthorized') {
      alert('Error al guardar el APN: ' + err.message)
    }
  } finally {
    hideSpinner()
  }
}

const setRestartConfig = async restartData => {
  try {
    const response = await apiFetch('/command/setrestart', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(restartData),
    })
    const data = await response.json()

    if (data.status === 'success') {
      showModal('Reinicio programado', 'La configuracion se guardo correctamente.')
      if (RestartMsg) RestartMsg.textContent = 'OK: configuracion guardada.'
      if (data.RESTART) updateRestartPolicyHint(data.RESTART)
      setTimeout(() => {
        location.reload()
      }, 3000)
    } else {
      if (RestartMsg) RestartMsg.textContent = 'Error al guardar reinicio programado.'
      alert(data.message || 'Error al guardar el reinicio programado')
    }
  } catch (err) {
    if (RestartMsg) RestartMsg.textContent = 'Error al guardar reinicio programado.'
    if (err && err.message !== 'Unauthorized') {
      alert('Error al guardar el reinicio programado: ' + err.message)
    }
  } finally {
    hideSpinner()
  }
}

const setNetMode = async () => {
  showSpinner()
  if (NetModeMsg) NetModeMsg.textContent = ''

  try {
    const mode = parseInt(NetModeSelect.value)
    const response = await apiFetch('/command/setnetmode', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ mode }),
    })
    const data = await response.json()

    if (data.status === 'success') {
      showModal('Modo de red actualizado', 'El modo de red se actualizo correctamente.')
      setTimeout(() => {
        location.reload()
      }, 5000)
    } else {
      const msg = data.message || 'Error al cambiar el modo de red'
      if (NetModeMsg) {
        NetModeMsg.textContent = msg
      } else {
        alert(msg)
      }
    }
  } catch (err) {
    const msg =
      err && err.message && err.message !== 'Unauthorized'
        ? err.message
        : 'Error al cambiar el modo de red'
    if (NetModeMsg) {
      NetModeMsg.textContent = msg
    } else if (err && err.message !== 'Unauthorized') {
      alert(msg)
    }
  } finally {
    hideSpinner()
  }
}

const saveConfig = () => {
  showSpinner()

  const serialData = {
    RS485: {
      Puerto: parseInt(RS485Puerto.value),
      Vel: parseInt(RS485Vel.value),
      DataBit: parseInt(RS485DataBit.value),
      Paridad: parseInt(RS485Paridad.value),
      StopBit: parseInt(RS485StopBit.value),
      Timeout: parseInt(RS485Timeout.value),
    },
  }

  setSerialDataConfig(serialData)
}

const saveApn = () => {
  showSpinner()

  const apnData = {
    cid: parseInt(APNCid.value),
    pdp_type: APNPdp.value,
    apn: APNName.value,
    user: APNUser.value,
    password: APNPass.value,
    auth: parseInt(APNAuth.value),
  }

  setApnConfig(apnData)
}

const saveRestart = () => {
  showSpinner()
  if (RestartMsg) RestartMsg.textContent = ''

  const recoveryEnabled = NetworkRecoveryEnabled && NetworkRecoveryEnabled.value === '1'
  const restartData = {
    Enabled: RestartEnabled && RestartEnabled.value === '1',
    IntervalHours: parseInt(RestartHours.value),
    NetworkRecoveryEnabled: recoveryEnabled,
  }
  if (recoveryEnabled) {
    restartData.StackRestartAfterNoNetworkSec =
      parseInt(StackRestartMin ? StackRestartMin.value : '5', 10) * 60
    restartData.PowerRestartAfterNoNetworkSec =
      parseInt(PowerRestartMin ? PowerRestartMin.value : '15', 10) * 60
  }

  setRestartConfig(restartData)
}

const saveMqtt = () => {
  showSpinner()
  if (MqttMsg) MqttMsg.textContent = ''
  setMqttConfig(collectMqttFormData())
}

const testMqtt = async () => {
  const mqttData = collectMqttFormData()
  if (!mqttData.Host) {
    if (MqttMsg) MqttMsg.textContent = 'Ingrese el host del broker MQTT antes de probar.'
    alert('Ingrese el host del broker MQTT antes de probar.')
    return
  }

  if (MqttMsg) MqttMsg.textContent = 'Enviando mensaje de prueba MQTT...'
  showSpinner()

  try {
    const response = await apiFetch('/command/mqtt-test', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(mqttData),
      timeout: 60000,
    })

    let data = null
    const contentType = response.headers.get('content-type') || ''
    if (contentType.indexOf('application/json') >= 0) {
      data = await response.json()
    } else {
      const text = await response.text()
      const message =
        text && text.trim()
          ? text.trim()
          : 'Respuesta invalida del servidor (HTTP ' + response.status + ')'
      if (MqttMsg) MqttMsg.textContent = message
      alert(message)
      return
    }

    if (data.status === 'success') {
      const topic = data.topic || '-'
      if (MqttMsg) {
        MqttMsg.textContent = 'Prueba enviada al topic: ' + topic
      }
      showModal(
        'Prueba MQTT',
        'Mensaje de prueba enviado correctamente.\nTopic: ' + topic
      )
      return
    }

    const message =
      data.message || 'Error en prueba MQTT (HTTP ' + response.status + ')'
    if (MqttMsg) MqttMsg.textContent = message
    alert(message)
  } catch (err) {
    const message =
      err && err.message && err.message !== 'Unauthorized'
        ? err.message
        : 'No se pudo ejecutar la prueba MQTT'
    if (MqttMsg) MqttMsg.textContent = message
    if (err && err.message !== 'Unauthorized') alert(message)
  } finally {
    hideSpinner()
  }
}

const restartModem = async () => {
  showSpinner()

  try {
    const response = await apiFetch('/command/restartmodem', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    })
    const data = await response.json()

    if (data.status === 'success') {
      showModal('Modem reiniciado', 'El modem se ha reiniciado correctamente.')
      setTimeout(() => {
        location.reload()
      }, 15000)
    } else {
      alert(data.message || 'Error al reiniciar el modem')
    }
  } catch (err) {
    if (err && err.message !== 'Unauthorized') {
      alert('Error al reiniciar el modem: ' + err.message)
    }
  } finally {
    hideSpinner()
  }
}

const updateFotaUI = data => {
  if (!data || !FotaStatus || !FotaProgress) return

  const status = data.status || 'UNKNOWN'
  const message = data.message || ''
  const result = data.result
  let text = status

  if (message) text += ' - ' + message
  if (result !== undefined && result !== null && result !== '') {
    text += ' (codigo ' + result + ')'
  }

  FotaStatus.textContent = text
  if (data.progress !== undefined && data.progress !== null && data.progress !== '') {
    FotaProgress.textContent = data.progress + '%'
  } else {
    FotaProgress.textContent = ''
  }
}

const pollFotaStatus = async () => {
  try {
    const response = await apiFetch('/command/fota-status')
    if (!response.ok) return
    const data = await response.json()
    updateFotaUI(data)
  } catch (err) {
    // Sin ruido para no interrumpir interfaz
  }
}

const init = async () => {
  initSidebarLayout()
  initSidebar()
  showSpinner()
  try {
    const authenticated = await ensureAuth()
    if (!authenticated) return
    await getModemStatus()
    await getSerialDataConfig()
    await getApnConfig()
    await getRestartConfig()
    await getMqttConfig()
    await pollFotaStatus()
  } finally {
    hideSpinner()
  }
}

window.addEventListener('load', init)

if (NetworkRecoveryEnabled) {
  NetworkRecoveryEnabled.addEventListener('change', toggleNetworkRecoveryFields)
}

const logoutBtn = getById('logoutbtn')
if (logoutBtn) logoutBtn.onclick = logout

const refresh = getById('refresh')
if (refresh) {
  refresh.addEventListener('click', async () => {
    refresh.classList.add('refresh')
    await getModemStatus()
    refresh.classList.remove('refresh')
  })
}

const saveConfigBtn = getById('saveconfigbtn')
if (saveConfigBtn) saveConfigBtn.onclick = saveConfig

const saveApnBtn = getById('saveapnbtn')
if (saveApnBtn) saveApnBtn.onclick = saveApn

const setNetModeBtn = getById('setnetmodebtn')
if (setNetModeBtn) setNetModeBtn.onclick = setNetMode

const restartBtn = getById('restartbtn')
if (restartBtn) restartBtn.onclick = restartModem

const restartSaveBtn = getById('saverestartbtn')
if (restartSaveBtn) restartSaveBtn.onclick = saveRestart

const saveMqttBtn = getById('savemqttbtn')
if (saveMqttBtn) saveMqttBtn.onclick = saveMqtt

const testMqttBtn = getById('testmqttbtn')
if (testMqttBtn) testMqttBtn.onclick = testMqtt

if (FotaForm) {
  FotaForm.addEventListener('submit', async event => {
    event.preventDefault()
    showSpinner()

    try {
      const firmwareInput = getById('firmware_url')
      const params = new URLSearchParams()
      params.append('firmware_url', firmwareInput ? firmwareInput.value.trim() : '')

      const response = await apiFetch('/command/start-fota', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: params.toString(),
      })

      const text = await response.text()
      const plain = text.replace(/<[^>]*>/g, '').trim()
      if (plain && FotaStatus) {
        FotaStatus.textContent = plain
      }
      await pollFotaStatus()
    } catch (err) {
      if (FotaStatus) {
        FotaStatus.textContent = 'Error iniciando FOTA'
      }
    } finally {
      hideSpinner()
    }
  })
}

setInterval(() => {
  const fotaPanel = getById('panel-fota')
  if (fotaPanel && fotaPanel.classList.contains('active')) {
    pollFotaStatus()
  }
}, 5000)
