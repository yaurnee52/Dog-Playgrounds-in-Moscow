const userInfo = document.getElementById("userInfo");
const dogsList = document.getElementById("dogsList");
const showAddDogBtn = document.getElementById("showAddDogBtn");
const addDogCard = document.getElementById("addDogCard");
const addDogForm = document.getElementById("addDogForm");
const addDogStatus = document.getElementById("addDogStatus");
const cancelAddDog = document.getElementById("cancelAddDog");
const logoutBtn = document.getElementById("logoutBtn");

function showStatus(message, isSuccess) {
  addDogStatus.textContent = message;
  addDogStatus.classList.remove("d-none", "alert-success", "alert-danger");
  addDogStatus.classList.add(isSuccess ? "alert-success" : "alert-danger");
}

async function loadUser() {
  try {
    const response = await axios.get("/api/me");
    const user = response.data;
    userInfo.innerHTML = `
      <div><strong>Логин:</strong> ${user.username}</div>
      <div><strong>Email:</strong> ${user.email}</div>
    `;
  } catch (error) {
    window.location.href = "/";
  }
}

async function loadDogs() {
  dogsList.innerHTML = "";
  try {
    const response = await axios.get("/api/my-dogs");
    const dogs = response.data || [];
    if (!dogs.length) {
      dogsList.innerHTML = "<div class=\"text-muted\">Питомцы не добавлены.</div>";
      return;
    }
    dogs.forEach((dog) => {
      const item = document.createElement("div");
      item.className = "list-group-item";
      item.innerHTML = `
        <div class="fw-semibold">${dog.name}</div>
        <div class="small text-muted">${dog.category_code} ${dog.breed ? `• ${dog.breed}` : ""}</div>
      `;
      dogsList.appendChild(item);
    });
  } catch (error) {
    dogsList.innerHTML = "<div class=\"text-danger\">Ошибка загрузки.</div>";
  }
}

showAddDogBtn.addEventListener("click", () => {
  addDogCard.classList.remove("d-none");
});

cancelAddDog.addEventListener("click", () => {
  addDogCard.classList.add("d-none");
  addDogStatus.classList.add("d-none");
  addDogForm.reset();
});

addDogForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(addDogForm);
  const payload = Object.fromEntries(formData.entries());
  try {
    await axios.post("/api/dogs/add", payload);
    showStatus("Питомец добавлен.", true);
    addDogForm.reset();
    await loadDogs();
  } catch (error) {
    const message = error.response?.data?.error || "Не удалось добавить питомца.";
    showStatus(message, false);
  }
});

logoutBtn.addEventListener("click", async () => {
  await axios.post("/api/logout");
  window.location.href = "/";
});

loadUser();
loadDogs();
