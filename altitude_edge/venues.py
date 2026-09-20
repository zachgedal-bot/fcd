"""
Home-venue altitude (metres) for clubs and national teams in the leagues where
altitude is a live pricing question. Values are the stadium's approximate
elevation; where a club shares a city ground the city figure is used.

Sources: club/stadium pages, Wikipedia stadium articles, CNN (El Alto 4,090 m),
StadiumDB (Estadio Banco Guayaquil 2,517 m), Mushuc Runa club site (3,250 m).
Treat every figure as +/- 50 m.

`habitual` marks teams whose league schedule regularly takes them to
>2,000 m (Liga MX, Bolivia, Ecuador, Colombia, Peru domestic). The scanner
applies a habituation discount to them, per Alanis et al. 2022 (one Liga MX
club showed flat running across altitude zones over 130 matches).
"""
import unicodedata

VENUES = {
    # ---------------- Liga MX ----------------
    "Toluca": ("Toluca", 2670, "MEX"),
    "Pachuca": ("Pachuca", 2430, "MEX"),
    "Puebla": ("Puebla", 2135, "MEX"),
    "America": ("Mexico City", 2240, "MEX"),
    "Cruz Azul": ("Mexico City", 2240, "MEX"),
    "Pumas UNAM": ("Mexico City", 2270, "MEX"),
    "Atlante": ("Mexico City", 2240, "MEX"),
    "Queretaro": ("Queretaro", 1820, "MEX"),
    "Leon": ("Leon", 1800, "MEX"),
    "Guadalajara": ("Zapopan", 1560, "MEX"),
    "Atlas": ("Guadalajara", 1560, "MEX"),
    "Atletico San Luis": ("San Luis Potosi", 1860, "MEX"),
    "Necaxa": ("Aguascalientes", 1880, "MEX"),
    "Juarez": ("Ciudad Juarez", 1140, "MEX"),
    "Santos Laguna": ("Torreon", 1120, "MEX"),
    "Monterrey": ("Guadalupe", 540, "MEX"),
    "Tigres UANL": ("San Nicolas de los Garza", 500, "MEX"),
    "Tijuana": ("Tijuana", 20, "MEX"),
    "Mazatlan": ("Mazatlan", 10, "MEX"),
    # ---------------- Bolivia ----------------
    "Always Ready": ("El Alto", 4090, "BOL"),
    "Bolivar": ("La Paz", 3637, "BOL"),
    "The Strongest": ("La Paz", 3637, "BOL"),
    "Academia del Balompie Boliviano": ("La Paz", 3637, "BOL"),
    "Nacional Potosi": ("Potosi", 3960, "BOL"),
    "Real Potosi": ("Potosi", 3960, "BOL"),
    "Real Oruro": ("Oruro", 3735, "BOL"),
    "GV San Jose": ("Oruro", 3735, "BOL"),
    "Universitario de Vinto": ("Vinto", 2560, "BOL"),
    "Aurora": ("Cochabamba", 2560, "BOL"),
    "Wilstermann": ("Cochabamba", 2560, "BOL"),
    "Independiente Petrolero": ("Sucre", 2800, "BOL"),
    "Real Tomayapo": ("Tarija", 1850, "BOL"),
    "Oriente Petrolero": ("Santa Cruz", 415, "BOL"),
    "Blooming": ("Santa Cruz", 415, "BOL"),
    "Real Santa Cruz": ("Santa Cruz", 415, "BOL"),
    "Guabira": ("Montero", 300, "BOL"),
    "San Antonio Bulo Bulo": ("Bulo Bulo", 250, "BOL"),
    # ---------------- Ecuador ----------------
    "LDU Quito": ("Quito", 2850, "ECU"),
    "Aucas": ("Quito", 2850, "ECU"),
    "Universidad Catolica": ("Quito", 2850, "ECU"),
    "El Nacional": ("Quito", 2850, "ECU"),
    "Vinotinto": ("Quito", 2850, "ECU"),
    "Independiente del Valle": ("Sangolqui", 2517, "ECU"),
    "Deportivo Cuenca": ("Cuenca", 2560, "ECU"),
    "Macara": ("Ambato", 2580, "ECU"),
    "Tecnico Universitario": ("Ambato", 2580, "ECU"),
    "Mushuc Runa": ("Echaleche", 3250, "ECU"),
    "Libertad": ("Loja", 2060, "ECU"),
    "Barcelona SC": ("Guayaquil", 4, "ECU"),
    "Emelec": ("Guayaquil", 4, "ECU"),
    "Orense": ("Machala", 6, "ECU"),
    "Delfin": ("Manta", 6, "ECU"),
    "Manta FC": ("Manta", 6, "ECU"),
    # ---------------- Colombia ----------------
    "Millonarios": ("Bogota", 2640, "COL"),
    "Santa Fe": ("Bogota", 2640, "COL"),
    "Fortaleza CEIF": ("Bogota", 2640, "COL"),
    "La Equidad": ("Bogota", 2640, "COL"),
    "Boyaca Chico": ("Tunja", 2820, "COL"),
    "Patriotas": ("Tunja", 2820, "COL"),
    "Deportivo Pasto": ("Pasto", 2527, "COL"),
    "Once Caldas": ("Manizales", 2150, "COL"),
    "Aguilas Doradas": ("Rionegro", 2125, "COL"),
    "Envigado": ("Envigado", 1575, "COL"),
    "Atletico Nacional": ("Medellin", 1495, "COL"),
    "Independiente Medellin": ("Medellin", 1495, "COL"),
    "Deportivo Pereira": ("Pereira", 1410, "COL"),
    "Deportes Tolima": ("Ibague", 1285, "COL"),
    "America de Cali": ("Cali", 995, "COL"),
    "Deportivo Cali": ("Palmira", 1000, "COL"),
    "Atletico Bucaramanga": ("Bucaramanga", 960, "COL"),
    "Llaneros": ("Villavicencio", 467, "COL"),
    "Cucuta Deportivo": ("Cucuta", 320, "COL"),
    "Alianza Valledupar": ("Valledupar", 169, "COL"),
    "Junior": ("Barranquilla", 18, "COL"),
    "Jaguares": ("Monteria", 18, "COL"),
    "Union Magdalena": ("Santa Marta", 6, "COL"),
    # ---------------- Peru ----------------
    "Cienciano": ("Cusco", 3400, "PER"),
    "Cusco FC": ("Cusco", 3400, "PER"),
    "Deportivo Garcilaso": ("Cusco", 3400, "PER"),
    "Sport Huancayo": ("Huancayo", 3250, "PER"),
    "ADT": ("Tarma", 3050, "PER"),
    "Los Chankas": ("Andahuaylas", 2900, "PER"),
    "Ayacucho FC": ("Ayacucho", 2760, "PER"),
    "UTC Cajamarca": ("Cajamarca", 2750, "PER"),
    "FC Cajamarca": ("Cajamarca", 2750, "PER"),
    "Comerciantes Unidos": ("Cutervo", 2650, "PER"),
    "Melgar": ("Arequipa", 2335, "PER"),
    "Deportivo Moquegua": ("Moquegua", 1410, "PER"),
    "Juan Pablo II": ("Chongoyape", 250, "PER"),
    "Alianza Lima": ("Lima", 150, "PER"),
    "Universitario": ("Lima", 150, "PER"),
    "Sporting Cristal": ("Lima", 150, "PER"),
    "Sport Boys": ("Callao", 5, "PER"),
    "Alianza Atletico": ("Sullana", 60, "PER"),
    "Atletico Grau": ("Piura", 30, "PER"),
    # ------- CONMEBOL club opponents (low altitude, for cup ties) -------
    "Boca Juniors": ("Buenos Aires", 25, "ARG"),
    "River Plate": ("Buenos Aires", 25, "ARG"),
    "Racing Club": ("Avellaneda", 15, "ARG"),
    "Independiente": ("Avellaneda", 15, "ARG"),
    "San Lorenzo": ("Buenos Aires", 25, "ARG"),
    "Estudiantes": ("La Plata", 20, "ARG"),
    "Velez Sarsfield": ("Buenos Aires", 25, "ARG"),
    "Lanus": ("Lanus", 20, "ARG"),
    "Talleres": ("Cordoba", 400, "ARG"),
    "Flamengo": ("Rio de Janeiro", 5, "BRA"),
    "Fluminense": ("Rio de Janeiro", 5, "BRA"),
    "Botafogo": ("Rio de Janeiro", 5, "BRA"),
    "Vasco da Gama": ("Rio de Janeiro", 5, "BRA"),
    "Palmeiras": ("Sao Paulo", 760, "BRA"),
    "Corinthians": ("Sao Paulo", 760, "BRA"),
    "Sao Paulo": ("Sao Paulo", 760, "BRA"),
    "Santos": ("Santos", 5, "BRA"),
    "Atletico Mineiro": ("Belo Horizonte", 850, "BRA"),
    "Cruzeiro": ("Belo Horizonte", 850, "BRA"),
    "Gremio": ("Porto Alegre", 10, "BRA"),
    "Internacional": ("Porto Alegre", 10, "BRA"),
    "Colo-Colo": ("Santiago", 570, "CHI"),
    "Universidad de Chile": ("Santiago", 570, "CHI"),
    "Universidad Catolica Chile": ("Santiago", 570, "CHI"),
    "Penarol": ("Montevideo", 40, "URU"),
    "Nacional": ("Montevideo", 40, "URU"),
    "Montevideo City Torque": ("Montevideo", 40, "URU"),
    "Olimpia": ("Asuncion", 45, "PAR"),
    "Cerro Porteno": ("Asuncion", 45, "PAR"),
    "Libertad Paraguay": ("Asuncion", 45, "PAR"),
    "Caracas FC": ("Caracas", 900, "VEN"),
    "Deportivo Tachira": ("San Cristobal", 830, "VEN"),
    # ---------------- National teams (usual home venue) ----------------
    "Bolivia": ("El Alto", 4090, "NT"),
    "Ecuador": ("Quito", 2850, "NT"),
    "Colombia": ("Barranquilla", 18, "NT"),
    "Peru": ("Lima", 150, "NT"),
    "Mexico": ("Mexico City", 2240, "NT"),
    "Argentina": ("Buenos Aires", 25, "NT"),
    "Brazil": ("various", 300, "NT"),
    "Chile": ("Santiago", 570, "NT"),
    "Uruguay": ("Montevideo", 40, "NT"),
    "Paraguay": ("Asuncion", 45, "NT"),
    "Venezuela": ("Maturin", 65, "NT"),
}

HABITUAL_LEAGUES = {"MEX", "BOL", "ECU", "COL", "PER"}

ALIASES = {
    "club america": "America",
    "cf america": "America",
    "deportivo toluca": "Toluca",
    "toluca fc": "Toluca",
    "cf pachuca": "Pachuca",
    "club puebla": "Puebla",
    "pumas": "Pumas UNAM",
    "unam": "Pumas UNAM",
    "chivas": "Guadalajara",
    "cd guadalajara": "Guadalajara",
    "club tijuana": "Tijuana",
    "xolos": "Tijuana",
    "tigres": "Tigres UANL",
    "cf monterrey": "Monterrey",
    "rayados": "Monterrey",
    "fc juarez": "Juarez",
    "club leon": "Leon",
    "club necaxa": "Necaxa",
    "san luis": "Atletico San Luis",
    "mazatlan fc": "Mazatlan",
    "queretaro fc": "Queretaro",
    "club bolivar": "Bolivar",
    "abb": "Academia del Balompie Boliviano",
    "academia del balompie": "Academia del Balompie Boliviano",
    "liga de quito": "LDU Quito",
    "ldu": "LDU Quito",
    "liga deportiva universitaria": "LDU Quito",
    "sd aucas": "Aucas",
    "u catolica": "Universidad Catolica",
    "universidad catolica del ecuador": "Universidad Catolica",
    "idv": "Independiente del Valle",
    "cs emelec": "Emelec",
    "delfin sc": "Delfin",
    "orense sc": "Orense",
    "millonarios fc": "Millonarios",
    "independiente santa fe": "Santa Fe",
    "fortaleza": "Fortaleza CEIF",
    "chico fc": "Boyaca Chico",
    "boyaca chico fc": "Boyaca Chico",
    "pasto": "Deportivo Pasto",
    "junior fc": "Junior",
    "junior de barranquilla": "Junior",
    "nacional medellin": "Atletico Nacional",
    "dim": "Independiente Medellin",
    "america cali": "America de Cali",
    "utc": "UTC Cajamarca",
    "utc de cajamarca": "UTC Cajamarca",
    "cusco": "Cusco FC",
    "garcilaso": "Deportivo Garcilaso",
    "huancayo": "Sport Huancayo",
    "fbc melgar": "Melgar",
    "universitario de deportes": "Universitario",
    "u de chile": "Universidad de Chile",
    "colo colo": "Colo-Colo",
}


def _norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(s.lower().replace(".", " ").split())


_INDEX = {_norm(k): k for k in VENUES}
_INDEX.update({_norm(k): v for k, v in ALIASES.items()})


def lookup(name):
    """Return (canonical_name, city, altitude_m, league) or None."""
    key = _norm(name)
    canon = _INDEX.get(key)
    if canon is None:
        # substring fallback: 'Deportivo Toluca FC' -> 'toluca'
        for k, v in _INDEX.items():
            if k in key or key in k:
                canon = v
                break
    if canon is None:
        return None
    city, alt, lg = VENUES[canon]
    return canon, city, alt, lg


def is_habitual(league_code):
    return league_code in HABITUAL_LEAGUES


def high_altitude_teams(min_alt=2000):
    return sorted(((n, c, a, l) for n, (c, a, l) in VENUES.items() if a >= min_alt), key=lambda r: -r[2])


if __name__ == "__main__":
    for n, c, a, l in high_altitude_teams():
        print(f"{a:5d} m  {n:35s} {c:25s} {l}")
