const map = L.map("map").setView([55.75, 37.62], 11);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

const modalElement = document.getElementById("playgroundModal");
const modal = new bootstrap.Modal(modalElement);

const titleEl = document.getElementById("modalTitle");
const addressEl = document.getElementById("modalAddress");
const metaEl = document.getElementById("modalMeta");
const photoEl = document.getElementById("modalPhoto");
const slotsContainer = document.getElementById("slotsContainer");
const categorySelect = document.getElementById("categorySelect");
const dogSelect = document.getElementById("dogSelect");

let currentPlaygroundId = null;
let dogsCache = [];
let dogsById = {};

async function loadPlaygrounds() {
  const urlParams = new URLSearchParams(window.location.search);
  const district = urlParams.get("district");
  let response;
  try {
    response = await axios.get("/api/playgrounds", {
      params: district ? { district } : {},
    });
  } catch (error) {
    alert("Не удалось загрузить площадки.");
    return;
  }
  const bounds = L.latLngBounds([]);
  response.data.forEach((playground) => {
    if (playground.lat && playground.lon) {
      const marker = L.marker([playground.lat, playground.lon])
        .addTo(map)
        .on("click", () => openPlayground(playground.id));
      bounds.extend(marker.getLatLng());
    }
  });
  if (bounds.isValid()) {
    map.fitBounds(bounds.pad(0.15));
  }
}

async function openPlayground(playgroundId) {
  currentPlaygroundId = playgroundId;
  await loadDogs();
  await loadDetails();
  modal.show();
}

async function loadDetails() {
  if (!currentPlaygroundId) {
    return;
  }
  const category = categorySelect.value;
  const dogId = dogSelect.value;
  const response = await axios.get(
    `/api/playgrounds/${currentPlaygroundId}/details`,
    { params: { category, dog_id: dogId || undefined } }
  );
  renderModal(response.data);
}

function renderModal(details) {
  titleEl.textContent = details.park_name && details.park_name !== "[]"
    ? details.park_name
    : `Площадка №${details.id}`;
  addressEl.textContent = details.address || "Адрес не указан";

  const metaParts = [];
  if (details.district) metaParts.push(details.district);
  if (details.adm_area) metaParts.push(details.adm_area);
  if (details.working_hours) metaParts.push(details.working_hours.replaceAll("\n", " "));
  metaEl.textContent = metaParts.join(" • ");

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
    button.className = `btn btn-sm slot-btn ${statusToClass(slot.status)}`;
    button.textContent = `${slot.label} (${slot.count}/${slot.limit})`;
    button.disabled = slot.status === "full";
    button.addEventListener("click", () => bookSlot(slot.hour));
    slotsContainer.appendChild(button);
  });
}

function statusToClass(status) {
  if (status === "free") return "btn-success";
  if (status === "joinable") return "btn-warning";
  return "btn-danger";
}

async function bookSlot(hour) {
  const dogId = dogSelect.value;
  if (!dogId) {
    alert("Выберите собаку для бронирования.");
    return;
  }
  try {
    await axios.post("/api/book", {
      playground_id: currentPlaygroundId,
      slot_hour: hour,
      dog_id: dogId,
    });
    await loadDetails();
  } catch (error) {
    const message =
      error.response?.data?.error || "Не удалось записаться на слот.";
    alert(message);
  }
}

async function loadDogs() {
  if (dogsCache.length) {
    return;
  }
  const response = await axios.get("/api/dogs");
  dogsCache = response.data || [];
  dogsById = dogsCache.reduce((acc, dog) => {
    acc[String(dog.id)] = dog;
    return acc;
  }, {});

  dogSelect.innerHTML = "";
  const emptyOption = document.createElement("option");
  emptyOption.value = "";
  emptyOption.textContent = "Выберите собаку";
  dogSelect.appendChild(emptyOption);

  dogsCache.forEach((dog) => {
    const option = document.createElement("option");
    option.value = dog.id;
    option.textContent = `${dog.name} (${dog.category_code})`;
    dogSelect.appendChild(option);
  });
}

categorySelect.addEventListener("change", () => {
  loadDetails();
});

dogSelect.addEventListener("change", () => {
  const selectedDog = dogsById[dogSelect.value];
  if (selectedDog && selectedDog.category_code) {
    categorySelect.value = selectedDog.category_code;
  }
  loadDetails();
});

loadPlaygrounds();
