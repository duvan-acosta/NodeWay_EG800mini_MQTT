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
const RestartMsg = document.getElementById('restart_msg')
const navStatusText = document.getElementById('nav_status_text')

const getById = id => document.getElementById(id)

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
    const response = await fetch('/command/getmodemstatus')
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
  const response = await fetch('/command/getconfig')
  const data = await response.json()

  if (RS485Puerto) RS485Puerto.value = String(data.RS485.Puerto)
  if (RS485Vel) RS485Vel.value = String(data.RS485.Vel)
  if (RS485DataBit) RS485DataBit.value = String(data.RS485.DataBit)
  if (RS485Paridad) RS485Paridad.value = String(data.RS485.Paridad)
  if (RS485StopBit) RS485StopBit.value = String(data.RS485.StopBit)
  if (RS485Timeout) RS485Timeout.value = String(data.RS485.Timeout)
}

const getApnConfig = async () => {
  const response = await fetch('/command/getapn')
  const data = await response.json()

  if (APNCid) APNCid.value = String(data.cid || 1)
  if (APNPdp) {
    const pdpValue = data.pdp_type_str || data.pdp_type || 'IP'
    APNPdp.value = String(pdpValue)
  }
  if (APNName) APNName.value = data.apn || ''
  if (APNUser) APNUser.value = data.user || ''
  if (APNPass) APNPass.value = data.password || ''
  if (APNAuth) APNAuth.value = String(data.auth ?? 0)
}

const getRestartConfig = async () => {
  const response = await fetch('/command/getrestart')
  const data = await response.json()
  if (RestartEnabled) RestartEnabled.value = data.Enabled ? '1' : '0'
  if (RestartHours) RestartHours.value = String(data.IntervalHours || 12)
}

const setSerialDataConfig = async serialData => {
  const response = await fetch('/command/setconfig', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(serialData),
  })
  const data = await response.json()

  hideSpinner()
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
}

const setApnConfig = async apnData => {
  try {
    const response = await fetch('/command/setapn', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(apnData),
    })
    const data = await response.json()

    hideSpinner()
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
    hideSpinner()
    alert('Error al guardar el APN: ' + err.message)
  }
}

const setRestartConfig = async restartData => {
  const response = await fetch('/command/setrestart', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(restartData),
  })
  const data = await response.json()

  hideSpinner()
  if (data.status === 'success') {
    showModal('Reinicio programado', 'La configuracion se guardo correctamente.')
    if (RestartMsg) RestartMsg.textContent = 'OK: configuracion guardada.'
    setTimeout(() => {
      location.reload()
    }, 3000)
  } else {
    if (RestartMsg) RestartMsg.textContent = 'Error al guardar reinicio programado.'
    alert(data.message || 'Error al guardar el reinicio programado')
  }
}

const setNetMode = async () => {
  showSpinner()
  if (NetModeMsg) NetModeMsg.textContent = ''

  const mode = parseInt(NetModeSelect.value)
  const response = await fetch('/command/setnetmode', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ mode }),
  })
  const data = await response.json()

  hideSpinner()
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

  const restartData = {
    Enabled: RestartEnabled && RestartEnabled.value === '1',
    IntervalHours: parseInt(RestartHours.value),
  }

  setRestartConfig(restartData)
}

const restartModem = async () => {
  showSpinner()

  const response = await fetch('/command/restartmodem', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  })
  const data = await response.json()

  hideSpinner()
  if (data.status === 'success') {
    showModal('Modem reiniciado', 'El modem se ha reiniciado correctamente.')
    setTimeout(() => {
      location.reload()
    }, 15000)
  } else {
    alert(data.message || 'Error al reiniciar el modem')
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
    const response = await fetch('/command/fota-status')
    if (!response.ok) return
    const data = await response.json()
    updateFotaUI(data)
  } catch (err) {
    // Sin ruido para no interrumpir interfaz
  }
}

const init = async () => {
  showSpinner()
  try {
    await getModemStatus()
    await getSerialDataConfig()
    await getApnConfig()
    await getRestartConfig()
    await pollFotaStatus()
  } finally {
    hideSpinner()
  }
}

window.addEventListener('load', init)

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

if (FotaForm) {
  FotaForm.addEventListener('submit', async event => {
    event.preventDefault()
    showSpinner()

    try {
      const firmwareInput = getById('firmware_url')
      const params = new URLSearchParams()
      params.append('firmware_url', firmwareInput ? firmwareInput.value.trim() : '')

      const response = await fetch('/command/start-fota', {
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

setInterval(pollFotaStatus, 5000)
