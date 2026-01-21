let map = null;

function initMap() {
  if (typeof DG === "undefined") {
    alert("Не удалось загрузить карту 2ГИС. Проверьте API ключ.");
    return;
  }
  DG.then(() => {
    map = DG.map("map", {
      center: [55.75, 37.62],
      zoom: 11,
    });
    loadPlaygrounds();
  });
}

const modalElement = document.getElementById("playgroundModal");
const modal = new bootstrap.Modal(modalElement);

const titleEl = document.getElementById("modalTitle");
const addressEl = document.getElementById("modalAddress");
const metaEl = document.getElementById("modalMeta");
const photoEl = document.getElementById("modalPhoto");
const slotsContainer = document.getElementById("slotsContainer");
const dogSelect = document.getElementById("dogSelect");
const dogSelectContainer = document.getElementById("dogSelectContainer");
const bookingAuthWarning = document.getElementById("bookingAuthWarning");
const bookSlotBtn = document.getElementById("bookSlotBtn");
const authModalElement = document.getElementById("authModal");
const authModalDialog = document.querySelector("#authModal .modal-dialog");
const loginForm = document.getElementById("loginForm");
const registerForm = document.getElementById("registerForm");
const authStatus = document.getElementById("authStatus");
const authTitle = document.getElementById("authTitle");
const showRegisterBtn = document.getElementById("showRegisterBtn");
const showLoginBtn = document.getElementById("showLoginBtn");
const profileLink = document.getElementById("profileLink");
const authButtons = document.querySelectorAll("[data-auth-button]");

let currentPlaygroundId = null;
let dogsCache = [];
let dogsById = {};
let selectedSlotHour = null;

let currentMarkers = [];

async function loadPlaygrounds() {
  if (!map) {
    return; 
  }
  

  currentMarkers.forEach(marker => {
    try {
      map.removeLayer(marker);
    } catch (e) {

    }
  });
  currentMarkers = [];
  
  const urlParams = new URLSearchParams(window.location.search);
  const district = urlParams.get("district");
  
  const params = district ? { district } : {};
  
  // Добавляем фильтры
  const lightingCheckbox = document.getElementById("mapFilterLighting");
  const fencingCheckbox = document.getElementById("mapFilterFencing");
  const elementsCheckbox = document.getElementById("mapFilterElements");
  
  if (lightingCheckbox && lightingCheckbox.checked) {
    params.lighting = "1";
  }
  if (fencingCheckbox && fencingCheckbox.checked) {
    params.fencing = "1";
  }
  if (elementsCheckbox && elementsCheckbox.checked) {
    params.elements = "1";
  }
  
  console.log("Загрузка площадок с параметрами:", params);
  
  let response;
  try {
    response = await axios.get("/api/playgrounds", { params });
    console.log("Получено площадок на карте:", response.data?.length || 0);
  } catch (error) {
    console.error("Ошибка загрузки площадок:", error);
    alert("Не удалось загрузить площадки.");
    return;
  }
  const bounds = [];
  response.data.forEach((playground) => {
    if (playground.lat && playground.lon) {
      const marker = DG.marker([playground.lat, playground.lon]).addTo(map);
      marker.on("click", () => openPlayground(playground.id));
      currentMarkers.push(marker);
      bounds.push([playground.lat, playground.lon]);
    }
  });
  if (bounds.length) {
    map.fitBounds(bounds, { padding: [30, 30] });
  }
}

async function loadDistricts() {
  const select = document.getElementById("mapDistrictSelect");
  if (!select) {
    return;
  }
  try {
    const response = await axios.get("/api/districts");
    const districts = response.data || [];
    
    select.innerHTML = '<option value="">Выберите район...</option>';
    
    districts.forEach((district) => {
      const option = document.createElement("option");
      option.value = district;
      option.textContent = district;
      select.appendChild(option);
    });
    
    const ts = new TomSelect(select, {
        create: false,
        sortField: {
          field: "text",
          direction: "asc"
        },
        placeholder: "Выберите район...",
        allowEmptyOption: true
    });
    
    const urlParams = new URLSearchParams(window.location.search);
    const currentDistrict = urlParams.get("district");
    if (currentDistrict) {
      ts.setValue(currentDistrict);
    }
    
    bindDistrictFilter();
  } catch (error) {
    console.error("Ошибка загрузки районов", error);
  }
}

function bindDistrictFilter() {
  const select = document.getElementById("mapDistrictSelect");
  const applyBtn = document.getElementById("mapDistrictApply");
  if (!select || !applyBtn) {
    return;
  }
  applyBtn.addEventListener("click", () => {
    const district = select.value;
    if (district) {
      window.location.href = `/map?district=${encodeURIComponent(district)}`;
    }
  });
  

  const lightingCheckbox = document.getElementById("mapFilterLighting");
  const fencingCheckbox = document.getElementById("mapFilterFencing");
  const elementsCheckbox = document.getElementById("mapFilterElements");
  
  console.log("Привязка обработчиков фильтров:", {
    lighting: !!lightingCheckbox,
    fencing: !!fencingCheckbox,
    elements: !!elementsCheckbox
  });
  
  if (lightingCheckbox) {
    lightingCheckbox.addEventListener("change", () => {
      console.log("Фильтр освещение изменен:", lightingCheckbox.checked);
      if (map) {
        loadPlaygrounds();
      }
    });
  }
  if (fencingCheckbox) {
    fencingCheckbox.addEventListener("change", () => {
      console.log("Фильтр ограждение изменен:", fencingCheckbox.checked);
      if (map) {
        loadPlaygrounds();
      }
    });
  }
  if (elementsCheckbox) {
    elementsCheckbox.addEventListener("change", () => {
      console.log("Фильтр элементы изменен:", elementsCheckbox.checked);
      if (map) {
        loadPlaygrounds();
      }
    });
  }
}

async function checkAuth() {
  try {
    await axios.get("/api/me");
    if (profileLink) {
      profileLink.classList.remove("d-none");
    }
    authButtons.forEach((btn) => btn.classList.add("d-none"));
  } catch (error) {
    if (profileLink) {
      profileLink.classList.add("d-none");
    }
    authButtons.forEach((btn) => btn.classList.remove("d-none"));
  }
}

async function openPlayground(playgroundId) {
  currentPlaygroundId = playgroundId;
  selectedSlotHour = null;
  bookSlotBtn.disabled = true;
  await loadDogs();
  await loadDetails();
  modal.show();
}

async function loadDetails() {
  if (!currentPlaygroundId) {
    return;
  }
  const dogId = dogSelect.value;
  const response = await axios.get(
    `/api/playgrounds/${currentPlaygroundId}/details`,
    { params: { dog_id: dogId || undefined } }
  );
  renderModal(response.data);
}

function formatWorkingHours(workingHours) {
  if (!workingHours) return null;
  
  const hours = workingHours.match(/Hours:([^\n]+)/g);
  if (!hours || hours.length === 0) return null;
  
  const uniqueHours = [...new Set(hours.map(h => h.replace('Hours:', '').trim()))];
  
  if (uniqueHours.length === 1) {
    return uniqueHours[0] === 'круглосуточно' ? 'Круглосуточно' : `Пн-Вс: ${uniqueHours[0]}`;
  }
  
  return uniqueHours.join(', ');
}

function renderModal(details) {
  titleEl.textContent = details.park_name && details.park_name !== "[]"
    ? details.park_name
    : `Площадка №${details.id}`;
  addressEl.textContent = details.address || "Адрес не указан";

  const metaParts = [];
  if (details.district) metaParts.push(details.district);
  if (details.adm_area) metaParts.push(details.adm_area);
  metaEl.textContent = metaParts.join(" • ");
    const workingHoursFormatted = formatWorkingHours(details.working_hours);
  let workingHoursEl = document.getElementById("modalWorkingHours");
  
  if (workingHoursFormatted) {

    if (!workingHoursEl) {
      workingHoursEl = document.createElement("p");
      workingHoursEl.id = "modalWorkingHours";
      workingHoursEl.className = "text-muted mb-3";

      if (metaEl.nextSibling) {
        metaEl.parentNode.insertBefore(workingHoursEl, metaEl.nextSibling);
      } else {
        metaEl.parentNode.appendChild(workingHoursEl);
      }
    }
    workingHoursEl.innerHTML = `<strong>Режим работы:</strong> ${workingHoursFormatted}`;
    workingHoursEl.classList.remove("d-none");
  } else {

    if (workingHoursEl) {
      workingHoursEl.classList.add("d-none");
    }
  }

  if (details.photo_url) {
    photoEl.src = details.photo_url;
    photoEl.classList.remove("d-none");
  } else {
    photoEl.classList.add("d-none");
  }

  slotsContainer.innerHTML = "";
  details.slots.forEach((slot) => {
    const button = document.createElement("button");
    button.type = "button";
    const isSelected = selectedSlotHour === slot.hour;
    button.className = `btn btn-sm slot-btn ${statusToClass(slot.status, isSelected)}`;
    button.textContent = `${slot.label} (${slot.count}/${slot.limit})`;
    
    const canBook = dogsCache.length > 0 && dogSelect.value;
    button.disabled = slot.status === "full" || !canBook;

    if (!button.disabled) {
      button.addEventListener("click", () => selectSlot(slot.hour));
    }
    slotsContainer.appendChild(button);
  });
}

function selectSlot(hour) {
  selectedSlotHour = hour;
  bookSlotBtn.disabled = false;
  loadDetails(); 
}

function statusToClass(status, isSelected) {
  if (isSelected) return "btn-primary";
  if (status === "free") return "btn-success";
  if (status === "joinable") return "btn-warning";
  return "btn-danger";
}

async function bookSlot() {
  const dogId = dogSelect.value;
  if (!dogId) {
    alert("Выберите собаку для бронирования.");
    return;
  }
  if (selectedSlotHour === null) {
      alert("Выберите время.");
      return;
  }

  try {
    await axios.post("/api/book", {
      playground_id: currentPlaygroundId,
      slot_hour: selectedSlotHour,
      dog_id: dogId,
    });
    alert("Вы успешно записались!");
    selectedSlotHour = null;
    bookSlotBtn.disabled = true;
    await loadDetails();
  } catch (error) {
    const message =
      error.response?.data?.error || "Не удалось записаться на слот.";
    alert(message);
  }
}

async function loadDogs() {
  let isAuth = false;
  try {
      const response = await axios.get("/api/my-dogs");
      dogsCache = response.data || [];
      isAuth = true;
  } catch (e) {
      dogsCache = [];
      isAuth = false;
  }

  dogsById = dogsCache.reduce((acc, dog) => {
    acc[String(dog.id)] = dog;
    return acc;
  }, {});

  dogSelect.innerHTML = "";
  
  if (!isAuth) {
      dogSelectContainer.classList.add("d-none");
      bookSlotBtn.classList.add("d-none");
      if (bookingAuthWarning) {
        bookingAuthWarning.textContent = "Войдите в аккаунт, чтобы записаться.";
        bookingAuthWarning.classList.remove("d-none");
      }
      return;
  }
  
  if (dogsCache.length === 0) {
      dogSelectContainer.classList.add("d-none");
      bookSlotBtn.classList.add("d-none");
      if (bookingAuthWarning) {
        bookingAuthWarning.textContent = "У вас нет добавленных собак. Добавьте собаку в личном кабинете.";
        bookingAuthWarning.classList.remove("d-none");
      }
      return;
  }

  if (bookingAuthWarning) {
    bookingAuthWarning.classList.add("d-none");
  }
  
  dogSelectContainer.classList.remove("d-none");
  bookSlotBtn.classList.remove("d-none");

  dogsCache.forEach((dog) => {
    const option = document.createElement("option");
    option.value = dog.id;
    option.textContent = `${dog.name} (${dog.category_code})`;
    dogSelect.appendChild(option);
  });
  
  if (dogsCache.length > 0) {
      dogSelect.value = dogsCache[0].id;
  }
}

if (bookSlotBtn) {
  bookSlotBtn.addEventListener("click", bookSlot);
}

dogSelect.addEventListener("change", () => {

  selectedSlotHour = null;
  bookSlotBtn.disabled = true;
  loadDetails();
});

function showAuthStatus(message, isSuccess) {
  if (!authStatus) {
    return;
  }
  authStatus.textContent = message;
  authStatus.classList.remove("d-none", "alert-success", "alert-danger");
  authStatus.classList.add(isSuccess ? "alert-success" : "alert-danger");
}

function closeAuthModal() {
  if (!authModalElement) {
    return;
  }
  const instance =
    bootstrap.Modal.getInstance(authModalElement) ||
    new bootstrap.Modal(authModalElement);
  instance.hide();
}

function showLoginForm() {
  if (!loginForm || !registerForm) {
    return;
  }
  authTitle.textContent = "Авторизация";
  loginForm.classList.remove("d-none");
  registerForm.classList.add("d-none");
  showRegisterBtn.classList.remove("d-none");
  showLoginBtn.classList.add("d-none");
  if (authModalDialog) {
    authModalDialog.classList.remove("modal-lg");
    authModalDialog.classList.add("modal-md");
  }
}

function showRegisterForm() {
  if (!loginForm || !registerForm) {
    return;
  }
  authTitle.textContent = "Регистрация";
  registerForm.classList.remove("d-none");
  loginForm.classList.add("d-none");
  showRegisterBtn.classList.add("d-none");
  showLoginBtn.classList.remove("d-none");
  if (authModalDialog) {
    authModalDialog.classList.remove("modal-md");
    authModalDialog.classList.add("modal-lg");
  }
}

if (loginForm) {
  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(loginForm);
    const payload = Object.fromEntries(formData.entries());
    try {
      await axios.post("/api/login", payload);
      showAuthStatus("Успешный вход.", true);
      loginForm.reset();
      await checkAuth();
      closeAuthModal();
    } catch (error) {
      const message = error.response?.data?.error || "Ошибка авторизации.";
      showAuthStatus(message, false);
    }
  });
}

if (registerForm) {
  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(registerForm);
    const payload = Object.fromEntries(formData.entries());
    try {
      await axios.post("/api/register", payload);
      await axios.post("/api/login", {
        username: payload.username,
        password: payload.password,
      });
      showAuthStatus("Регистрация прошла успешно.", true);
      registerForm.reset();
      await checkAuth();
      closeAuthModal();
    } catch (error) {
      const message =
        error.response?.data?.error || "Не удалось зарегистрироваться.";
      showAuthStatus(message, false);
    }
  });
}

if (showRegisterBtn) {
  showRegisterBtn.addEventListener("click", showRegisterForm);
}
if (showLoginBtn) {
  showLoginBtn.addEventListener("click", showLoginForm);
}

if (authModalElement) {
  authModalElement.addEventListener("show.bs.modal", (event) => {
    const trigger = event.relatedTarget;
    const action = trigger?.getAttribute("data-auth-action");
    if (action === "register") {
      showRegisterForm();
    } else {
      showLoginForm();
    }
  });
}

async function checkUrlParams() {
  const urlParams = new URLSearchParams(window.location.search);
  const playgroundId = urlParams.get("playground_id");
  if (playgroundId) {
    await openPlayground(playgroundId);
  }
}


initMap();
loadDistricts(); 
checkAuth();
checkUrlParams();
