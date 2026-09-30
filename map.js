/* PaleoIMAGING Techniques Map */

"use strict";

const DATA_URL = "data/institutions.json";

const TECHNIQUES = [
  {
    name: "HSI",
    color: "#7b2cbf",
    patterns: [/\bhsi\b/i, /hyperspectral/i, /\bspecim\b/i, /\bhyspex\b/i]
  },
  {
    name: "XRF",
    color: "#d62828",
    patterns: [/\bxrf\b/i, /micro[\s-]?xrf/i, /µxrf/i, /μxrf/i, /\bavaatech\b/i, /\bitrax\b/i, /\btornado\b/i]
  },
  {
    name: "CT",
    color: "#2a9d8f",
    patterns: [/\bct\b/i, /micro[\s-]?ct/i, /µct/i, /μct/i, /computed tomography/i]
  },
  {
    name: "MSCL",
    color: "#f4a261",
    patterns: [/\bmscl\b/i, /multi[\s-]?sensor core logger/i, /\bgeotek\b/i]
  },
  {
    name: "MSI",
    color: "#457b9d",
    patterns: [/\bmsi\b/i, /multispectral/i]
  },
  {
    name: "LA-ICP-MS",
    color: "#e9c46a",
    patterns: [/la[\s-]?icp[\s-]?ms/i, /laser ablation.*icp/i]
  },
  {
    name: "LIBS",
    color: "#264653",
    patterns: [/\blibs\b/i, /laser[\s-]?induced breakdown spectroscopy/i]
  },
  {
    name: "SEM-EDS",
    color: "#6c757d",
    patterns: [/\bsem\b/i, /\beds\b/i, /sem[\s-]?eds/i, /electron microscopy/i]
  }
];

const FALLBACK_TECHNIQUE = {
  name: "Other",
  color: "#495057"
};

function escapeHtml(value) {
  if (value === null || value === undefined) {
    return "";
  }

  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function detectTechniques(record) {
  const searchableText = [
    record.equipment,
    record.other_instruments,
    record.available_protocols
  ]
    .filter(Boolean)
    .join(" ");

  const detected = TECHNIQUES.filter((technique) =>
    technique.patterns.some((pattern) => pattern.test(searchableText))
  );

  return detected.length ? detected : [FALLBACK_TECHNIQUE];
}

function createTechniqueIcon(techniques) {
  const dots = techniques
    .map(
      (technique) =>
        `<span
          title="${escapeHtml(technique.name)}"
          style="
            display:inline-block;
            width:12px;
            height:12px;
            border-radius:50%;
            background:${technique.color};
            border:1.5px solid #ffffff;
            box-shadow:0 1px 3px rgba(0,0,0,.35);
            margin:-1px;
          "
        ></span>`
    )
    .join("");

  const size = Math.max(22, 12 + (techniques.length - 1) * 8);

  return L.divIcon({
    className: "",
    html: `
      <div
        style="
          display:flex;
          align-items:center;
          justify-content:center;
          min-width:${size}px;
          height:24px;
          padding:2px 4px;
          border-radius:14px;
          background:rgba(255,255,255,.92);
          border:1px solid rgba(31,41,51,.2);
          box-shadow:0 2px 6px rgba(0,0,0,.22);
          white-space:nowrap;
        "
      >
        ${dots}
      </div>
    `,
    iconSize: [size, 24],
    iconAnchor: [size / 2, 12],
    popupAnchor: [0, -14]
  });
}

function textRow(label, value) {
  if (!value) {
    return "";
  }

  return `
    <p>
      <span class="popup-label">${escapeHtml(label)}:</span>
      ${escapeHtml(value)}
    </p>
  `;
}

function createPopup(record, techniques) {
  const institution =
    record.institution || record.laboratory || "Unnamed institution";

  const laboratory =
    record.laboratory && record.laboratory !== record.institution
      ? `<p>${escapeHtml(record.laboratory)}</p>`
      : "";

  const techniqueList = techniques
    .map(
      (technique) =>
        `<span style="
          display:inline-block;
          margin:2px 4px 2px 0;
          padding:2px 7px;
          border-radius:10px;
          background:${technique.color};
          color:#fff;
          font-size:.78rem;
          font-weight:600;
        ">${escapeHtml(technique.name)}</span>`
    )
    .join("");

  const email = record.email
    ? `<p><span class="popup-label">Email:</span>
       <a href="mailto:${escapeHtml(record.email)}">${escapeHtml(record.email)}</a></p>`
    : "";

  return `
    <div>
      <h3>${escapeHtml(institution)}</h3>
      ${laboratory}
      ${textRow("Country", record.country)}

      <p>
        <span class="popup-label">Techniques:</span><br>
        ${techniqueList}
      </p>

      ${textRow("Equipment", record.equipment)}
      ${textRow("Available protocols", record.available_protocols)}
      ${textRow(
        "Interlaboratory comparison readiness",
        record.interlaboratory_comparison_readiness
      )}
      ${textRow("Contact", record.contact_person)}
      ${email}
    </div>
  `;
}

function addLegend(map) {
  const legend = L.control({ position: "bottomright" });

  legend.onAdd = function () {
    const container = L.DomUtil.create("div");
    container.style.background = "rgba(255,255,255,.95)";
    container.style.padding = "10px 12px";
    container.style.borderRadius = "8px";
    container.style.boxShadow = "0 2px 8px rgba(0,0,0,.18)";
    container.style.fontSize = "12px";
    container.style.lineHeight = "1.5";

    const rows = [...TECHNIQUES, FALLBACK_TECHNIQUE]
      .map(
        (technique) => `
          <div style="display:flex;align-items:center;gap:7px;">
            <span style="
              width:10px;
              height:10px;
              border-radius:50%;
              background:${technique.color};
              display:inline-block;
              flex:0 0 auto;
            "></span>
            <span>${escapeHtml(technique.name)}</span>
          </div>
        `
      )
      .join("");

    container.innerHTML = `
      <div style="font-weight:700;margin-bottom:5px;">Techniques</div>
      ${rows}
    `;

    L.DomEvent.disableClickPropagation(container);
    return container;
  };

  legend.addTo(map);
}

async function loadInstitutions() {
  const response = await fetch(DATA_URL, { cache: "no-store" });

  if (!response.ok) {
    throw new Error(
      `Could not load ${DATA_URL} (HTTP ${response.status}).`
    );
  }

  return response.json();
}

async function initializeMap() {
  const statusElement = document.getElementById("map-status");

  const map = L.map("map", {
    worldCopyJump: true,
    minZoom: 2
  }).setView([25, 5], 2);

  L.tileLayer(
    "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    {
      maxZoom: 19,
      attribution:
        "Tiles &copy; Esri — Sources: Esri, Maxar, Earthstar Geographics, and the GIS User Community"
    }
  ).addTo(map);

  addLegend(map);

  try {
    const institutions = await loadInstitutions();
    const bounds = [];
    let plotted = 0;

    for (const record of institutions) {
      const latitude = Number(record.latitude);
      const longitude = Number(record.longitude);

      if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
        console.warn("Skipping record without valid coordinates:", record);
        continue;
      }

      const techniques = detectTechniques(record);
      const marker = L.marker([latitude, longitude], {
        icon: createTechniqueIcon(techniques),
        title: record.institution || record.laboratory || "Institution"
      });

      marker.bindPopup(createPopup(record, techniques), {
        maxWidth: 380
      });

      marker.addTo(map);
      bounds.push([latitude, longitude]);
      plotted += 1;
    }

    if (bounds.length > 0) {
      map.fitBounds(bounds, {
        padding: [40, 40],
        maxZoom: 4
      });
    }

    statusElement.textContent =
      `${plotted} institutions displayed from ${institutions.length} records.`;
  } catch (error) {
    console.error(error);

    statusElement.textContent =
      "Could not load the institutional dataset. See the browser console for details.";
  }
}

initializeMap();
