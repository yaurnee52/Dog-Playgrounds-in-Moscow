const userInfo = document.getElementById("userInfo");
const dogsList = document.getElementById("dogsList");
const showAddDogBtn = document.getElementById("showAddDogBtn");
const addDogForm = document.getElementById("addDogForm");
const addDogStatus = document.getElementById("addDogStatus");
const submitAddDogBtn = document.getElementById("submitAddDogBtn");
const logoutBtn = document.getElementById("logoutBtn");
const addDogModal = new bootstrap.Modal(document.getElementById("addDogModal"));

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
  addDogStatus.classList.add("d-none");
  addDogForm.reset();
  addDogModal.show();
});

submitAddDogBtn.addEventListener("click", async () => {
  const formData = new FormData(addDogForm);
  const payload = Object.fromEntries(formData.entries());
  try {
    await axios.post("/api/dogs/add", payload);
    showStatus("Питомец добавлен.", true);
    addDogForm.reset();
    await loadDogs();
    setTimeout(() => {
      addDogModal.hide();
    }, 1000);
  } catch (error) {
    const message = error.response?.data?.error || "Не удалось добавить питомца.";
    showStatus(message, false);
  }
});

logoutBtn.addEventListener("click", async () => {
  await axios.post("/api/logout");
  window.location.href = "/";
});

const bookingsList = document.getElementById("bookingsList");

async function loadBookings() {
  bookingsList.innerHTML = "";
  try {
    const response = await axios.get("/api/my-bookings");
    const bookings = response.data || [];
    if (!bookings.length) {
      bookingsList.innerHTML = "<div class=\"text-muted\">История записей пуста.</div>";
      return;
    }
    bookings.forEach((booking) => {
      const item = document.createElement("div");
      item.className = "list-group-item";
      
      const dateObj = new Date(booking.start_time);
      const dateStr = dateObj.toLocaleDateString();
      const timeStr = dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      const parkName =
        booking.park_name && booking.park_name !== "[]"
          ? booking.park_name
          : `Площадка №${booking.playground_id}`;

      item.innerHTML = `
        <div class="d-flex w-100 justify-content-between">
            <h6 class="mb-1">${parkName}</h6>
            <small class="text-muted">${dateStr} ${timeStr}</small>
        </div>
        <p class="mb-1 small text-muted">${booking.address || ""}</p>
        <small class="text-primary">Собака: ${booking.dog_name}</small>
      `;
      bookingsList.appendChild(item);
    });
  } catch (error) {
    bookingsList.innerHTML = "<div class=\"text-danger\">Ошибка загрузки истории.</div>";
  }
}

loadUser();
loadDogs();
loadBookings();