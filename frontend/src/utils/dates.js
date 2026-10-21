const dateLocale = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();

// « Aujourd'hui », « Hier » ou « mardi 6 octobre 2026 »
export const libelleJour = (iso, maintenant = new Date()) => {
  const d = new Date(iso);
  const ecart = Math.round((dateLocale(maintenant) - dateLocale(d)) / 86400000);
  if (ecart === 0) return "Aujourd'hui";
  if (ecart === 1) return 'Hier';
  return d.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
};

export const heure = (iso) => new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });

export const cleJour = (iso) => {
  const d = new Date(iso);
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
};
