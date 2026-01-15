const districtSelect = document.getElementById("districtSelect");
const searchBtn = document.getElementById("searchBtn");
const openMapBtn = document.getElementById("openMapBtn");
const searchResults = document.getElementById("searchResults");
const loginForm = document.getElementById("loginForm");
const registerForm = document.getElementById("registerForm");
const showRegisterBtn = document.getElementById("showRegisterBtn");
const showLoginBtn = document.getElementById("showLoginBtn");
const authStatus = document.getElementById("authStatus");
const authTitle = document.getElementById("authTitle");
const authModalDialog = document.querySelector("#authModal .modal-dialog");
const authModal = document.getElementById("authModal");

async function loadDistricts() {
  let districts = [];
  try {
    const response = await axios.get("/api/districts");
    districts = response.data || [];
  } catch (error) {
    searchResults.innerHTML =
      "<div class=\"text-danger\">Не удалось загрузить районы.</div>";
    return;
  }
  districtSelect.innerHTML = "";
  districts.forEach((district, index) => {
    const option = document.createElement("option");
    option.value = district;
    option.textContent = district;
    if (index === 0) {
      option.selected = true;
    }
    districtSelect.appendChild(option);
  });
  updateMapLink();
}

function updateMapLink() {
  const district = districtSelect.value;
  openMapBtn.href = district ? `/map?district=${encodeURIComponent(district)}` : "/map";
}

async function searchPlaygrounds() {
  const district = districtSelect.value;
  if (!district) {
    return;
  }
  try {
    const response = await axios.get("/api/playgrounds/search", {
      params: { district },
    });
    renderResults(response.data || [], district);
  } catch (error) {
    searchResults.innerHTML =
      "<div class=\"text-danger\">Ошибка поиска площадок.</div>";
  }
}

function renderResults(items, district) {
  searchResults.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "text-muted";
    empty.textContent = "Площадок не найдено.";
    searchResults.appendChild(empty);
    return;
  }
  items.forEach((item) => {
    const name =
      item.park_name && item.park_name !== "[]"
        ? item.park_name
        : `Площадка №${item.id}`;
    const link = document.createElement("a");
    link.className = "list-group-item list-group-item-action";
    link.href = `/map?district=${encodeURIComponent(district)}`;
    link.target = "_blank";
    link.rel = "noopener";

    const title = document.createElement("div");
    title.className = "fw-semibold";
    title.textContent = name;

    const address = document.createElement("div");
    address.className = "small text-muted";
    address.textContent = item.address || "Адрес не указан";

    link.appendChild(title);
    link.appendChild(address);
    searchResults.appendChild(link);
  });
}

function showAuthStatus(message, isSuccess) {
  authStatus.textContent = message;
  authStatus.classList.remove("d-none", "alert-success", "alert-danger");
  authStatus.classList.add(isSuccess ? "alert-success" : "alert-danger");
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(loginForm);
  const payload = Object.fromEntries(formData.entries());
  try {
    await axios.post("/api/login", payload);
    showAuthStatus("Успешный вход.", true);
    loginForm.reset();
  } catch (error) {
    const message = error.response?.data?.error || "Ошибка авторизации.";
    showAuthStatus(message, false);
  }
});

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(registerForm);
  const payload = Object.fromEntries(formData.entries());
  try {
    await axios.post("/api/register", payload);
    showAuthStatus("Регистрация прошла успешно.", true);
    registerForm.reset();
    showLoginForm();
  } catch (error) {
    const message =
      error.response?.data?.error || "Не удалось зарегистрироваться.";
    showAuthStatus(message, false);
  }
});

function showLoginForm() {
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

showRegisterBtn.addEventListener("click", showRegisterForm);
showLoginBtn.addEventListener("click", showLoginForm);

if (authModal) {
  authModal.addEventListener("show.bs.modal", (event) => {
    const trigger = event.relatedTarget;
    const action = trigger?.getAttribute("data-auth-action");
    if (action === "register") {
      showRegisterForm();
    } else {
      showLoginForm();
    }
  });
}

districtSelect.addEventListener("change", updateMapLink);
searchBtn.addEventListener("click", searchPlaygrounds);

loadDistricts();
