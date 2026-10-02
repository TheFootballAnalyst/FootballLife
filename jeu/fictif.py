"""Le monde fictif (PLAN.md § 4, ECONOMIE.md § 5) : un jeu qu'on a le droit de vendre.

Chaque carte garde tout ce qui vient du réel — son barème, son poste, son âge, son
pied, sa nationalité, son physique — et reçoit un NOM GÉNÉRÉ, déterministe (même
carte, même nom d'une base à l'autre), tiré de listes de prénoms et de noms par
nationalité, sans ressemblance voulue avec le vrai : un nom différent, pas déguisé.
Les clubs prennent le nom de leur ville (et leur année de fondation quand une
ville en a deux : « Manchester 1878 », « Manchester 1880 ») ; les compétitions,
le nom du pays (« Championnat d'Angleterre », traduit par l'écran).

Le mode est un paramètre de la base (`parametre.monde` : « reel » ou « fictif »).
`appliquer(jeu, saison, "fictif")` garde les vrais noms dans `nom_reel` et écrit
les noms fictifs dans `nom`, là où tout le jeu les lit ; « reel » les restaure.
Le jeu local garde le réel tant qu'on ne vend rien ; la version en ligne part
fictive.

Les mods, chez le joueur, dans `mods/` à la racine : `noms.csv` (player_id,nom),
`clubs.csv` (team_id,nom[,couleur]), `competitions.csv` (competition_id,nom),
`portraits/<player_id>.png`, `logos/<team_id>.png`. Lus s'ils existent, en mode
fictif. Le jeu ne fournit aucun de ces fichiers.
"""
from __future__ import annotations

import csv
import hashlib
import pathlib
import re
import unicodedata

RACINE = pathlib.Path(__file__).resolve().parents[1]
MODS = RACINE / "mods"

# --------------------------------------------------------------------------
# Les noms, par groupe de nationalités
# --------------------------------------------------------------------------
# ISO-3 → groupe de noms.  Un pays absent prend le groupe « monde » (anglais).
GROUPE_PAYS = {
    **{p: "fr" for p in ("FRA", "MCO")},
    **{p: "en" for p in ("ENG", "SCO", "WAL", "NIR", "IRL", "USA", "CAN", "AUS", "NZL", "JAM", "TRI")},
    **{p: "es" for p in ("ESP",)},
    **{p: "latam" for p in ("ARG", "URU", "COL", "CHI", "PER", "MEX", "PAR", "ECU", "VEN", "BOL", "CRC", "HON", "PAN", "GUA", "SLV", "CUB", "DOM")},
    **{p: "pt" for p in ("POR", "ANG", "MOZ", "CPV", "GNB")},
    **{p: "br" for p in ("BRA",)},
    **{p: "it" for p in ("ITA", "SMR")},
    **{p: "de" for p in ("GER", "AUT", "LIE")},
    **{p: "nl" for p in ("NED", "SUR", "CUW")},
    **{p: "be" for p in ("BEL", "LUX")},
    **{p: "ch" for p in ("SUI",)},
    **{p: "tr" for p in ("TUR",)},
    **{p: "scandi" for p in ("DEN", "NOR", "SWE", "FIN", "ISL")},
    **{p: "pl" for p in ("POL",)},
    **{p: "cz" for p in ("CZE", "SVK")},
    **{p: "hu" for p in ("HUN",)},
    **{p: "balkan" for p in ("CRO", "SRB", "BIH", "SVN", "MNE", "MKD", "KVX", "KOS", "ALB")},
    **{p: "gr" for p in ("GRE", "CYP")},
    **{p: "ro" for p in ("ROU", "MDA")},
    **{p: "est" for p in ("UKR", "RUS", "BLR", "BUL", "GEO", "ARM", "AZE", "KAZ", "LTU", "LVA", "EST", "UZB")},
    **{p: "sahel" for p in ("SEN", "MLI", "GUI", "BFA", "GAM", "MTN", "NIG")},
    **{p: "golfe" for p in ("CIV", "TOG", "BEN", "GHA", "NGA", "SLE", "LBR")},
    **{p: "centre" for p in ("CMR", "COD", "CGO", "GAB", "CTA", "CHA", "EQG", "RWA", "BDI")},
    **{p: "maghreb" for p in ("MAR", "ALG", "TUN", "EGY", "LBY")},
    **{p: "arabe" for p in ("KSA", "QAT", "UAE", "IRQ", "JOR", "LBN", "SYR", "PLE", "IRN")},
    **{p: "afrique_est" for p in ("KEN", "UGA", "TAN", "ETH", "SUD", "ZAM", "ZIM", "RSA", "MAD", "COM")},
    **{p: "jp" for p in ("JPN",)},
    **{p: "kr" for p in ("KOR",)},
    **{p: "asie" for p in ("CHN", "THA", "VIE", "PHI", "IDN", "MAS", "IND")},
}

NOMS: dict[str, tuple[list[str], list[str]]] = {
    "fr": (["Lucas", "Hugo", "Théo", "Nathan", "Enzo", "Louis", "Gabriel", "Jules", "Mathis", "Tom", "Noah", "Baptiste", "Clément", "Maxime", "Antoine", "Romain", "Julien", "Thomas", "Alexis", "Quentin", "Valentin", "Adrien", "Florian", "Mehdi", "Yanis", "Sofiane", "Rayan", "Idriss", "Kylian", "Mattéo"],
           ["Moreau", "Lefebvre", "Garnier", "Chevalier", "Fontaine", "Rousseau", "Blanchard", "Giraud", "Mercier", "Lambert", "Faure", "Marchand", "Dumont", "Carpentier", "Renard", "Lemoine", "Perrin", "Vidal", "Barbier", "Picard", "Gauthier", "Leclerc", "Collet", "Benoît", "Roussel", "Masson", "Delmas", "Aubert", "Guérin", "Noël", "Berger", "Rolland", "Vasseur", "Guillot", "Hamon", "Tessier", "Prévost", "Delorme", "Lacroix", "Bonnet"]),
    "en": (["Oliver", "Harry", "Jack", "George", "Charlie", "Alfie", "Freddie", "Archie", "Oscar", "Leo", "Theo", "Finley", "Harvey", "Mason", "Kai", "Reece", "Callum", "Jordan", "Connor", "Kieran", "Ethan", "Tyler", "Josh", "Ben", "Sam", "Jake", "Liam", "Aaron", "Ryan", "Owen"],
           ["Whitfield", "Hargreaves", "Pennington", "Ashworth", "Barlow", "Chadwick", "Dawson", "Fairclough", "Garside", "Holloway", "Kershaw", "Lonsdale", "Marsden", "Nuttall", "Oakes", "Pickering", "Radcliffe", "Sutcliffe", "Thackeray", "Underwood", "Wainwright", "Yardley", "Blakemore", "Cresswell", "Fenwick", "Greenhalgh", "Hartley", "Ingram", "Kendrick", "Lister", "Mottram", "Newby", "Ollerton", "Prescott", "Rowley", "Sedgwick", "Tomlinson", "Varley", "Whittle", "Wilmot"]),
    "es": (["Álvaro", "Iker", "Pablo", "Adrián", "Marcos", "Sergio", "Rubén", "Jorge", "Mario", "Javier", "Diego", "Raúl", "Ismael", "Aitor", "Unai", "Gorka", "Asier", "Jon", "Iñigo", "Mikel", "Nico", "Dani", "Víctor", "Hugo", "Martín", "Alejandro", "Carlos", "Guillermo", "Rodrigo", "Joel"],
           ["Arrieta", "Bermúdez", "Cantero", "Delgado", "Escudero", "Ferrer", "Galindo", "Herrador", "Ibarra", "Juárez", "Lastra", "Mendizábal", "Navarrete", "Olmedo", "Peñalver", "Quiroga", "Riquelme", "Salgado", "Tapia", "Urrutia", "Valbuena", "Zabaleta", "Aranda", "Bustos", "Carrascal", "Dorado", "Espejo", "Fuentes", "Garrido", "Hinojosa", "Lozano", "Montalvo", "Noguera", "Ortigosa", "Pastor", "Redondo", "Segura", "Toledano", "Villalba", "Zapata"]),
    "latam": (["Thiago", "Mateo", "Santino", "Benjamín", "Lautaro", "Joaquín", "Facundo", "Nicolás", "Agustín", "Tomás", "Valentín", "Franco", "Bruno", "Ezequiel", "Maximiliano", "Ignacio", "Gonzalo", "Matías", "Emiliano", "Juan", "Luciano", "Federico", "Ramiro", "Nahuel", "Lucas", "Brian", "Kevin", "Cristian", "Jhon", "Yeison"],
              ["Acosta", "Benítez", "Cabrera", "Domínguez", "Escobar", "Figueroa", "Godoy", "Herrera", "Ibáñez", "Ledesma", "Maldonado", "Núñez", "Ocampo", "Paredes", "Quintero", "Rivas", "Sosa", "Toledo", "Valdez", "Zárate", "Aguirre", "Barrios", "Castillo", "Duarte", "Espinoza", "Farías", "Gamboa", "Lagos", "Montoya", "Orellana", "Peralta", "Riquelme", "Salinas", "Tapia", "Villanueva", "Zúñiga", "Bustamante", "Cardozo", "Galarza", "Medina"]),
    "pt": (["Tiago", "Diogo", "Gonçalo", "Rúben", "Tomás", "Afonso", "Rodrigo", "Duarte", "Vasco", "Nuno", "Rafael", "Francisco", "Martim", "Guilherme", "Dinis", "Leandro", "Fábio", "Ricardo", "André", "Hélder", "Bruno", "Paulo", "Sérgio", "Miguel", "Pedro", "João", "Simão", "Henrique", "Lourenço", "Mateus"],
           ["Albuquerque", "Barroso", "Carvalhal", "Dourado", "Esteves", "Figueiredo", "Guimarães", "Leitão", "Macedo", "Nogueira", "Pacheco", "Quaresma", "Rebelo", "Sarmento", "Tavares", "Valente", "Xavier", "Abrantes", "Bettencourt", "Cordeiro", "Drummond", "Fonseca", "Gouveia", "Lacerda", "Magalhães", "Negrão", "Peixoto", "Resende", "Saraiva", "Teixeira", "Vilaça", "Azevedo", "Brandão", "Cunha", "Faria", "Godinho", "Lamas", "Mota", "Pimenta", "Serrão"]),
    "br": (["Caio", "Vinícius", "Gustavo", "Matheus", "Rafael", "Lucas", "Guilherme", "Felipe", "Eduardo", "Rodrigo", "Thiago", "Bruno", "Leonardo", "Danilo", "Everton", "Wesley", "Jefferson", "Kaio", "Igor", "Yuri", "Marcos", "Douglas", "Alisson", "Anderson", "Robson", "Jonathan", "Wellington", "Fabrício", "Wallace", "Davi"],
           ["Amorim", "Bastos", "Cardoso", "Dantas", "Espíndola", "Fagundes", "Góes", "Henriques", "Jardim", "Lacerda", "Monteiro", "Nascimento", "Ornelas", "Peixoto", "Queiroz", "Ramalho", "Siqueira", "Toledo", "Vasconcelos", "Zanetti", "Barbosa", "Camargo", "Dutra", "Freitas", "Guedes", "Lins", "Macedo", "Nunes", "Prado", "Ribas", "Sampaio", "Tenório", "Valadares", "Bezerra", "Coimbra", "Fraga", "Lemos", "Moraes", "Rangel", "Seixas"]),
    "it": (["Matteo", "Lorenzo", "Alessandro", "Riccardo", "Tommaso", "Francesco", "Andrea", "Gabriele", "Federico", "Leonardo", "Davide", "Marco", "Simone", "Nicolò", "Edoardo", "Pietro", "Giacomo", "Samuele", "Filippo", "Luca", "Michele", "Emanuele", "Cristian", "Daniele", "Stefano", "Alberto", "Giovanni", "Mattia", "Antonio", "Elia"],
           ["Abbiati", "Baldini", "Castellani", "De Angelis", "Fabbri", "Galimberti", "Lazzari", "Mancuso", "Nardi", "Orlandi", "Pellegrini", "Rinaldi", "Sartori", "Tedesco", "Vanoli", "Zanon", "Belotti", "Caruso", "Donati", "Ferraro", "Grassi", "Lombardo", "Marino", "Neri", "Pagano", "Ruggeri", "Salvi", "Trevisan", "Valenti", "Benedetti", "Cattaneo", "Fontana", "Guarino", "Longhi", "Mariani", "Palmieri", "Rizzi", "Serra", "Vitale", "Zucchi"]),
    "de": (["Jonas", "Finn", "Luca", "Leon", "Nico", "Tim", "Jan", "Lukas", "Felix", "Maximilian", "Paul", "Moritz", "Niklas", "Julian", "Florian", "Tobias", "Kevin", "Marcel", "Philipp", "Simon", "Jannik", "Malte", "Ole", "Lennart", "Mats", "Noah", "Elias", "David", "Fabian", "Robin"],
           ["Achterberg", "Bachmann", "Dittrich", "Ehlers", "Falkenrath", "Gerlach", "Hagedorn", "Jäger", "Kessler", "Lindner", "Mühlbauer", "Nowak", "Ostermann", "Pfeiffer", "Reinhardt", "Sauer", "Thalmann", "Ullrich", "Voigt", "Wenzel", "Ziegler", "Brandt", "Dörfler", "Engel", "Freitag", "Groß", "Hoffmann", "Krause", "Lorenz", "Marquardt", "Neubauer", "Opitz", "Petersen", "Rademacher", "Seidel", "Trautmann", "Vogel", "Winkler", "Zimmermann", "Böhm"]),
    "nl": (["Daan", "Sem", "Luuk", "Bram", "Thijs", "Jesse", "Lars", "Milan", "Ruben", "Stijn", "Teun", "Joris", "Sven", "Koen", "Niels", "Tijn", "Wout", "Gijs", "Floris", "Jurre", "Mees", "Siem", "Jens", "Pim", "Rick", "Tom", "Max", "Julian", "Mick", "Dylan"],
           ["Bakhuizen", "Van der Linden", "De Groot", "Verhoeven", "Jansen", "Mulder", "Van Dongen", "Peeters", "Smit", "Visser", "Vermeulen", "De Wit", "Van Leeuwen", "Hendriks", "Kuijpers", "Van Dijk", "Willems", "Brouwer", "Dekker", "Bosch", "Van den Berg", "Timmermans", "Koster", "Vos", "Prins", "Blom", "Kok", "Zwart", "Van Vliet", "Schouten", "Huisman", "Roos", "Kramer", "Van Loon", "Post", "Meijer", "Scholten", "Terpstra", "Boer", "Van der Meer"]),
    "be": (["Arthur", "Louis", "Noah", "Jules", "Lucas", "Liam", "Adam", "Victor", "Gabriel", "Mohamed", "Milan", "Nathan", "Mathis", "Raphaël", "Léon", "Aaron", "Senne", "Wout", "Lowie", "Jarne", "Seppe", "Lennert", "Tuur", "Robbe", "Ferre", "Ilias", "Yassine", "Dries", "Maarten", "Simon"],
           ["Vanderhaeghe", "De Smet", "Claeys", "Lemaire", "Dupont", "Vermeersch", "Goossens", "Deconinck", "Maes", "Wouters", "Peeters", "Janssens", "Mertens", "Willems", "Dubois", "Lambrechts", "Verstraete", "Declercq", "Jacobs", "Martens", "Lenaerts", "Hermans", "Aerts", "Michiels", "Pauwels", "Verhulst", "Vandenbroucke", "Delannoy", "Bauwens", "Lejeune", "Rousseau", "Thys", "Cools", "Segers", "Van Damme", "Bogaert", "Daems", "Geerts", "Nys", "Vrancken"]),
    "ch": (["Noah", "Liam", "Luca", "Matteo", "Leon", "Elias", "Nico", "Yannick", "Fabio", "Dario", "Silvan", "Remo", "Loris", "Joël", "Sandro", "Reto", "Cédric", "Nils", "Jonas", "Timo", "Marco", "Simon", "Luis", "Ivan", "Sven", "Benjamin", "Flavio", "Kevin", "Dominik", "Pascal"],
           ["Abegglen", "Brunner", "Degen", "Egli", "Frei", "Gasser", "Huber", "Imhof", "Keller", "Lüthi", "Meier", "Näf", "Odermatt", "Pfister", "Roth", "Schär", "Tanner", "Vogt", "Wyss", "Zbinden", "Aeschbacher", "Bürki", "Dubach", "Fankhauser", "Gerber", "Hofer", "Känzig", "Lanz", "Moser", "Rüegg", "Steiner", "Trüb", "Walder", "Zehnder", "Bernasconi", "Crivelli", "Fasel", "Marti", "Rochat", "Zufferey"]),
    "tr": (["Emre", "Burak", "Kerem", "Yusuf", "Arda", "Mert", "Berkay", "Enes", "Kaan", "Oğuz", "Umut", "Barış", "Furkan", "Serkan", "Hakan", "Cenk", "Taha", "Efe", "Eren", "Ozan", "Berat", "Alperen", "Doğan", "Yiğit", "Batuhan", "Halil", "Selim", "Tolga", "Volkan", "Uğur"],
           ["Aksoy", "Bayraktar", "Çetinkaya", "Demirci", "Erdoğan", "Gündoğdu", "Işık", "Karaca", "Koçak", "Özdemir", "Polat", "Sarıoğlu", "Taşkın", "Uzun", "Yalçın", "Yıldırım", "Acar", "Bozkurt", "Çelik", "Doğru", "Ergin", "Güler", "Kaplan", "Kurt", "Oktay", "Öztürk", "Şahin", "Tekin", "Ünal", "Yavuz", "Arslan", "Başaran", "Durmaz", "Gürbüz", "Kılıç", "Korkmaz", "Sezer", "Tunç", "Yücel", "Zengin"]),
    "scandi": (["Emil", "Oskar", "Magnus", "Mikkel", "Anders", "Jonas", "Rasmus", "Mads", "Kasper", "Frederik", "Lasse", "Morten", "Viktor", "Sander", "Jesper", "Henrik", "Tobias", "Simon", "Elias", "William", "Hugo", "Axel", "Oliver", "Niklas", "Joakim", "Andreas", "Marcus", "Eirik", "Ole", "Sindre"],
               ["Andreassen", "Bakke", "Christiansen", "Dahl", "Eriksen", "Fredriksen", "Gustafsson", "Halvorsen", "Isaksen", "Jakobsen", "Knudsen", "Lindqvist", "Madsen", "Nygaard", "Olsen", "Pedersen", "Rasmussen", "Sørensen", "Thorsen", "Vestergaard", "Åkesson", "Berglund", "Dalgaard", "Engström", "Fjeld", "Grønbæk", "Hjort", "Iversen", "Kristensen", "Ljung", "Mortensen", "Nørgaard", "Østergaard", "Røed", "Sandberg", "Toft", "Ullmann", "Wiklund", "Bjerre", "Haugen"]),
    "pl": (["Jakub", "Kacper", "Mateusz", "Bartosz", "Szymon", "Michał", "Patryk", "Dawid", "Kamil", "Krzysztof", "Piotr", "Tomasz", "Marcin", "Łukasz", "Maciej", "Adrian", "Dominik", "Filip", "Igor", "Oskar", "Przemysław", "Sebastian", "Wojciech", "Rafał", "Paweł", "Damian", "Karol", "Hubert", "Artur", "Mikołaj"],
           ["Adamczyk", "Brzeziński", "Czarnecki", "Dąbrowski", "Grabowski", "Jabłoński", "Kaczmarek", "Lewandowicz", "Mazur", "Nowicki", "Ostrowski", "Pawlak", "Sikora", "Tomczak", "Wiśniewski", "Zalewski", "Baran", "Chmielewski", "Duda", "Górski", "Jasiński", "Krajewski", "Malinowski", "Olszewski", "Piotrowski", "Sadowski", "Szymański", "Walczak", "Wróbel", "Zając", "Borowski", "Cieślak", "Kowalczyk", "Michalak", "Pietrzak", "Sobczak", "Urbański", "Wysocki", "Żak", "Kubiak"]),
    "cz": (["Jakub", "Tomáš", "Lukáš", "Ondřej", "Matěj", "Adam", "Filip", "David", "Martin", "Vojtěch", "Dominik", "Patrik", "Daniel", "Michal", "Petr", "Marek", "Jan", "Štěpán", "Kryštof", "Samuel", "Šimon", "Matúš", "Juraj", "Erik", "Richard", "Radek", "Pavel", "Jiří", "Milan", "Roman"],
           ["Bartoš", "Čermák", "Doležal", "Fiala", "Hájek", "Jelínek", "Kolář", "Kratochvíl", "Marek", "Němec", "Pokorný", "Procházka", "Růžička", "Sedláček", "Štěpánek", "Urban", "Vaněk", "Zeman", "Beneš", "Dvořák", "Holub", "Kadlec", "Krejčí", "Mašek", "Novotný", "Polák", "Říha", "Šimek", "Tichý", "Vlček", "Blažek", "Horák", "Kočí", "Král", "Macek", "Svoboda", "Toman", "Veselý", "Zahradník", "Ševčík"]),
    "hu": (["Bence", "Máté", "Levente", "Dominik", "Ádám", "Balázs", "Dániel", "Zsombor", "Marcell", "Milán", "Áron", "Botond", "Gergő", "Kristóf", "Zalán", "Tamás", "Péter", "Attila", "Gábor", "László", "Zoltán", "Krisztián", "Norbert", "Roland", "Richárd", "Barnabás", "Olivér", "Patrik", "Bálint", "Márk"],
           ["Balogh", "Farkas", "Horváth", "Juhász", "Kovács", "Lakatos", "Mészáros", "Molnár", "Oláh", "Papp", "Simon", "Szabó", "Takács", "Tóth", "Varga", "Vincze", "Bíró", "Fekete", "Gál", "Hegedűs", "Kiss", "Lukács", "Magyar", "Orsós", "Pintér", "Somogyi", "Szűcs", "Török", "Vass", "Fodor", "Bodnár", "Gulyás", "Halász", "Kelemen", "Nemes", "Pál", "Sipos", "Szalai", "Vörös", "Bakos"]),
    "balkan": (["Luka", "Marko", "Nikola", "Ivan", "Petar", "Stefan", "Filip", "Matej", "Josip", "Ante", "Dario", "Toni", "Bruno", "Lovro", "Roko", "Jakov", "Mateo", "Dino", "Leon", "Vedran", "Milan", "Aleksandar", "Nemanja", "Lazar", "Vuk", "Dušan", "Uroš", "Bojan", "Andrej", "Dejan"],
               ["Babić", "Čović", "Dragović", "Grgić", "Horvat", "Jurić", "Kovačević", "Lukić", "Marković", "Nikolić", "Pavlović", "Radić", "Stanković", "Tomić", "Vuković", "Zorić", "Barišić", "Delić", "Filipović", "Golubović", "Ilić", "Janković", "Krstić", "Matić", "Novak", "Perić", "Ristić", "Savić", "Šarić", "Vidović", "Bašić", "Cvetković", "Đurić", "Jelić", "Kostić", "Milić", "Petrović", "Simić", "Vlašić", "Živković"]),
    "gr": (["Giorgos", "Dimitris", "Nikos", "Kostas", "Christos", "Vasilis", "Panagiotis", "Alexandros", "Andreas", "Stavros", "Thanasis", "Petros", "Lefteris", "Michalis", "Manolis", "Sotiris", "Fotis", "Marios", "Stelios", "Spyros", "Antonis", "Ilias", "Tasos", "Lambros", "Nikolas", "Vangelis", "Dionysis", "Pavlos", "Orestis", "Kyriakos"],
           ["Alexiou", "Bakirtzis", "Christou", "Dimou", "Economou", "Fotopoulos", "Galanis", "Ioannou", "Karalis", "Lambrou", "Makris", "Nikolaou", "Oikonomou", "Papadakis", "Raptis", "Samaras", "Theodorou", "Vasileiou", "Zafeiris", "Antoniou", "Charalambous", "Doukas", "Georgiou", "Kaloudis", "Lazaridis", "Michailidis", "Petrou", "Sarris", "Tsakiris", "Xenakis", "Andreou", "Delis", "Floros", "Katsaros", "Marinos", "Pappas", "Stavrou", "Tzanis", "Vlachos", "Zervas"]),
    "ro": (["Andrei", "Alexandru", "Ștefan", "Mihai", "Răzvan", "Cristian", "Florin", "Ionuț", "Vlad", "Darius", "Denis", "Rareș", "Gabriel", "Daniel", "Adrian", "Bogdan", "Cătălin", "Cosmin", "Dragoș", "Marius", "Octavian", "Radu", "Sebastian", "Tudor", "Valentin", "Victor", "Claudiu", "Emanuel", "Iulian", "Nicolae"],
           ["Albu", "Barbu", "Ciobanu", "Dumitrescu", "Enache", "Florescu", "Grigore", "Iordache", "Lungu", "Manea", "Nistor", "Oprea", "Preda", "Rusu", "Stoica", "Tudose", "Ursu", "Voinea", "Zamfir", "Anghel", "Bucur", "Constantin", "Dinu", "Ene", "Georgescu", "Ionescu", "Lazăr", "Marin", "Nedelcu", "Pîrvu", "Sandu", "Toma", "Vasile", "Badea", "Chiriac", "Dobre", "Matei", "Neagu", "Stan", "Vlad"]),
    "est": (["Artem", "Dmytro", "Oleksandr", "Mykola", "Andriy", "Bohdan", "Yevhen", "Serhiy", "Vitaliy", "Denys", "Illia", "Maksym", "Nazar", "Ostap", "Pavlo", "Roman", "Taras", "Vladyslav", "Yaroslav", "Danylo", "Giorgi", "Luka", "Nika", "Davit", "Levan", "Sandro", "Temur", "Zurab", "Rustam", "Timur"],
           ["Bondarenko", "Horbunov", "Kovalenko", "Lysenko", "Melnyk", "Oliynyk", "Polishchuk", "Rudenko", "Savchenko", "Tkachenko", "Vasylenko", "Zinchuk", "Boyko", "Danylyuk", "Hnatyuk", "Kravets", "Marchenko", "Moroz", "Pavlenko", "Shevchuk", "Tymoshenko", "Yurchenko", "Beridze", "Gelashvili", "Kapanadze", "Lomidze", "Mikeladze", "Nozadze", "Tsiklauri", "Japaridze", "Kiknadze", "Mamulashvili", "Abuladze", "Dolidze", "Gogoladze", "Khutsishvili", "Maisuradze", "Razmadze", "Tabidze", "Zhordania"]),
    "sahel": (["Moussa", "Mamadou", "Ibrahima", "Ousmane", "Abdoulaye", "Cheikh", "Pape", "Modou", "Lamine", "Sadio", "Boubacar", "Amadou", "Seydou", "Bakary", "Souleymane", "Adama", "Issa", "Yacouba", "Drissa", "Moussa", "Abdou", "Alassane", "Oumar", "Idrissa", "Habib", "Mahamadou", "Sékou", "Famara", "Aliou", "Khalifa"],
              ["Diallo", "Ndiaye", "Sarr", "Gueye", "Faye", "Mbodj", "Sow", "Sy", "Thiam", "Niang", "Cissé", "Diouf", "Dieng", "Kane", "Mbaye", "Seck", "Wade", "Camara", "Diarra", "Keïta", "Sissoko", "Dembélé", "Traoré", "Coulibaly", "Konaté", "Sidibé", "Doumbia", "Fofana", "Sangaré", "Diakité", "Tounkara", "Kouyaté", "Soumaré", "Bagayoko", "Haïdara", "Maïga", "Touré", "Ballo", "Dansoko", "Sylla"]),
    "golfe": (["Kwame", "Kofi", "Yaw", "Kwesi", "Kojo", "Nana", "Emmanuel", "Daniel", "Samuel", "Joseph", "Chinedu", "Emeka", "Obinna", "Chukwu", "Ikenna", "Tobi", "Femi", "Seun", "Kelechi", "Uche", "Yao", "Koffi", "Kouamé", "Konan", "Ange", "Sylvain", "Wilfried", "Franck", "Didier", "Serge"],
              ["Mensah", "Asante", "Owusu", "Boateng", "Appiah", "Agyei", "Amoah", "Darko", "Frimpong", "Gyasi", "Okafor", "Okeke", "Eze", "Nwachukwu", "Obi", "Adebayo", "Adeyemi", "Balogun", "Olawale", "Oyelaran", "Kouassi", "Kouadio", "Koné", "Bamba", "Yao", "N'Guessan", "Zoro", "Tiéhi", "Gbagbo", "Aké", "Lawson", "Agbeko", "Dossou", "Hounkpatin", "Sessi", "Quaye", "Tetteh", "Ankrah", "Nketiah", "Ofori"]),
    "centre": (["Samuel", "Patrick", "Jean", "Christian", "Franck", "Aurélien", "Steve", "Olivier", "Dieudonné", "Landry", "Cédric", "Yannick", "Junior", "Arnaud", "Chancel", "Gaël", "Dylan", "Kévin", "Jordan", "Axel", "Brice", "Lionel", "Fabrice", "Rodrigue", "Serge", "Wilfried", "Benjamin", "Elie", "Nathan", "Joël"],
               ["Mbarga", "Nkoulou", "Essomba", "Ngando", "Mbassi", "Onana", "Eto'o", "Ekotto", "Fomo", "Tchato", "Mulumba", "Kabongo", "Ilunga", "Mbuyi", "Tshibanda", "Kalala", "Mutombo", "Nzuzi", "Lukusa", "Bakambu", "Mavinga", "Mbemba", "Ngoma", "Obiang", "Nguema", "Mba", "Ondo", "Bouanga", "Lemina", "Ndong", "Mbeki", "Essono", "Ngah", "Ewolo", "Makiese", "Bokila", "Kazadi", "Mpoku", "Tshimanga", "Wamba"]),
    "maghreb": (["Youssef", "Amine", "Mehdi", "Yassine", "Hamza", "Ayoub", "Zakaria", "Ismaïl", "Walid", "Bilal", "Sofiane", "Rayan", "Ilyas", "Anas", "Omar", "Karim", "Nabil", "Reda", "Achraf", "Adam", "Mohamed", "Ahmed", "Mahmoud", "Mostafa", "Tarek", "Ramy", "Hossam", "Salah", "Nizar", "Wassim"],
                ["Benali", "Bouazza", "El Idrissi", "Haddadi", "Khelifi", "Lahlou", "Mansouri", "Nejjar", "Ouazzani", "Rahmani", "Saidi", "Tazi", "Zerrouki", "Belkacem", "Chaoui", "Derbali", "Fekir", "Guessous", "Hamdaoui", "Jebali", "Kaddour", "Lamrani", "Messaoudi", "Nasri", "Rebai", "Sbai", "Toumi", "Zahraoui", "Amrani", "Bensaid", "Cherkaoui", "Dahmani", "El Fassi", "Gharbi", "Hariri", "Jelassi", "Kacem", "Mezhoud", "Riahi", "Trabelsi"]),
    "arabe": (["Salem", "Khalid", "Faisal", "Abdullah", "Saud", "Turki", "Fahad", "Nasser", "Majed", "Sultan", "Yasser", "Bandar", "Hassan", "Hussein", "Ali", "Omar", "Mohammed", "Ahmad", "Tariq", "Zaid", "Reza", "Mehdi", "Sardar", "Amir", "Saman", "Milad", "Hamid", "Ehsan", "Kaveh", "Navid"],
              ["Al-Dosari", "Al-Ghamdi", "Al-Harbi", "Al-Mutairi", "Al-Otaibi", "Al-Qahtani", "Al-Shehri", "Al-Zahrani", "Al-Amri", "Al-Juhani", "Al-Khalifa", "Al-Mansoori", "Al-Nuaimi", "Al-Rashidi", "Al-Suwaidi", "Haddad", "Khoury", "Nasser", "Saleh", "Yousef", "Azmoun", "Ghaderi", "Hosseini", "Jahanbakhsh", "Karimi", "Moradi", "Rezaei", "Sadeghi", "Taheri", "Zarei", "Al-Awadhi", "Al-Balushi", "Al-Hashimi", "Al-Kuwari", "Al-Marri", "Darwish", "Fares", "Ibrahim", "Mansour", "Rahimi"]),
    "afrique_est": (["Victor", "Michael", "Dennis", "Brian", "Kevin", "Ayub", "Collins", "Joseph", "Eric", "Patrick", "Thabo", "Sipho", "Themba", "Lebo", "Bongani", "Percy", "Lyle", "Teboho", "Kagiso", "Keagan", "Mbwana", "Simon", "Rashid", "Abdul", "Juma", "Hassan", "Yusuf", "Zablon", "Fred", "Moses"],
                    ["Wanyama", "Omondi", "Otieno", "Ochieng", "Mwangi", "Kamau", "Njoroge", "Odhiambo", "Kipchoge", "Mutua", "Dlamini", "Nkosi", "Mokoena", "Zulu", "Mahlangu", "Khumalo", "Mthembu", "Sithole", "Ndlovu", "Mabena", "Samatta", "Msuva", "Kibwana", "Mwakalebela", "Ulimwengu", "Okwi", "Onyango", "Kizito", "Ssekamatte", "Lwanga", "Rakotondrabe", "Andriamanana", "Rajaonarison", "Banda", "Phiri", "Mwila", "Chirwa", "Tembo", "Musonda", "Lungu"]),
    "jp": (["Haruto", "Yuto", "Sota", "Yuki", "Hayato", "Ren", "Kaito", "Takumi", "Riku", "Daiki", "Shota", "Kenta", "Ryota", "Keisuke", "Takuya", "Kota", "Shun", "Yuya", "Koki", "Taiga", "Ayase", "Reo", "Jun", "Hiroki", "Naoki", "Kazuki", "Tatsuya", "Makoto", "Yudai", "Wataru"],
           ["Aoyama", "Fujimoto", "Hasegawa", "Ishikawa", "Kawamura", "Kobayashi", "Matsuoka", "Nakajima", "Okamoto", "Sakamoto", "Takahashi", "Uchida", "Watanabe", "Yamaguchi", "Yoshida", "Abe", "Endo", "Fukuda", "Hirano", "Inoue", "Kimura", "Maeda", "Morita", "Nishimura", "Ogawa", "Saito", "Sugiyama", "Taniguchi", "Ueda", "Yamashita", "Arai", "Baba", "Goto", "Hayashi", "Iwata", "Kondo", "Miura", "Nomura", "Shimizu", "Tsuchiya"]),
    "kr": (["Min-jun", "Seo-jun", "Ji-ho", "Ye-jun", "Do-yun", "Ha-jun", "Si-woo", "Jun-seo", "Hyun-woo", "Ji-hoon", "Dong-hyun", "Seung-min", "Jae-won", "Tae-yang", "Woo-jin", "Sung-min", "Young-jun", "Jin-woo", "Kyung-min", "Sang-hyun", "Joon-ho", "Hyun-jin", "Min-seok", "In-beom", "Kang-in", "Heung-min", "Ui-jo", "Chang-hoon", "Jae-sung", "Seung-gyu"],
           ["Kim", "Lee", "Park", "Choi", "Jung", "Kang", "Cho", "Yoon", "Jang", "Lim", "Han", "Oh", "Seo", "Shin", "Kwon", "Hwang", "Ahn", "Song", "Yoo", "Hong", "Jeon", "Moon", "Bae", "Baek", "Heo", "Nam", "Noh", "Ryu", "Son", "Yang", "Koo", "Min", "Byun", "Cha", "Chun", "Do", "Ha", "Jin", "Ko", "Woo"]),
    "asie": (["Wei", "Hao", "Jun", "Ming", "Lei", "Yang", "Bo", "Tao", "Jie", "Peng", "Somchai", "Anan", "Kittisak", "Teerasil", "Chanathip", "Minh", "Quang", "Tuan", "Duc", "Hoang", "Rizky", "Egy", "Bagus", "Dimas", "Arif", "Faiz", "Hakim", "Syafiq", "Arjun", "Sunil"],
             ["Wang", "Zhang", "Liu", "Chen", "Yang", "Zhao", "Huang", "Zhou", "Wu", "Xu", "Srisuk", "Bunmathan", "Dangda", "Kaewprom", "Phonsa", "Nguyen", "Tran", "Le", "Pham", "Hoang", "Saputra", "Pratama", "Wijaya", "Santoso", "Firmansyah", "Rahman", "Ismail", "Hassan", "Chhetri", "Jhingan"]),
    "monde": (["Daniel", "David", "Michael", "Alex", "Chris", "Martin", "Nicolas", "Adam", "Marco", "Leo", "Ivan", "Samuel", "Max", "Tom", "Noah", "Ben", "Jonas", "Felix", "Oscar", "Elias", "Luca", "Mateo", "Rafael", "Victor", "Simon", "Eric", "Sebastian", "Kevin", "Robin", "Julian"],
              ["Adler", "Baxter", "Carter", "Doran", "Ellis", "Fischer", "Grant", "Hale", "Irwin", "Jensen", "Keane", "Lane", "Mercer", "Nash", "Osborne", "Parker", "Quinn", "Reed", "Stone", "Turner", "Vance", "Walsh", "Young", "Archer", "Brooks", "Cole", "Dalton", "Everett", "Foster", "Hayes", "Lowe", "Marsh", "Norris", "Payne", "Rhodes", "Shaw", "Tate", "Webb", "Wells", "Yates"]),
}


def _h(cle: str) -> int:
    return int(hashlib.sha1(cle.encode("utf-8")).hexdigest(), 16)


def nom_joueur(pid: int, pays: str | None, exclus: set[str] | None = None, sel: int = 0) -> str:
    """Le nom fictif d'une carte : déterministe (pid), prénom et nom tirés du groupe
    de sa nationalité, un nom composé une fois sur quatre.  Une carte sans
    nationalité prend le groupe « monde ».  `exclus` : des noms à ne pas donner
    (les vrais noms de la base, les noms déjà pris) — on retire alors avec un sel,
    toujours de la même façon pour la même carte."""
    groupe = GROUPE_PAYS.get((pays or "").upper(), "monde")
    prenoms, noms = NOMS[groupe]
    for essai in range(sel, sel + 50):
        h = _h(f"joueur:{pid}:{essai}" if essai else f"joueur:{pid}")
        prenom = prenoms[h % len(prenoms)]
        nom = noms[(h // 1000) % len(noms)]
        if (h // 1_000_000) % 4 == 0:
            autre = noms[(h // 1_000_000_000) % len(noms)]
            if autre != nom:
                nom = f"{nom}-{autre}"
        complet = f"{prenom} {nom}"
        if not exclus or complet not in exclus:
            return complet
    return f"{prenom} {nom}"


def normaliser(nom: str) -> str:
    s = unicodedata.normalize("NFKD", nom)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


# --------------------------------------------------------------------------
# Les clubs : la ville, et l'année de fondation quand la ville en a plusieurs
# --------------------------------------------------------------------------
# nom réel → (ville, année ou None).  L'année ne sert qu'à distinguer deux clubs
# d'une même ville ; une ville à un club garde son seul nom.
VILLES: dict[str, tuple[str, int | None]] = {
    # Angleterre
    "Arsenal": ("Londres", 1886), "Chelsea": ("Londres", 1905), "Tottenham Hotspur": ("Londres", 1882), "West Ham United": ("Londres", 1895),
    "Fulham": ("Londres", 1879), "Crystal Palace": ("Londres", 1905), "Brentford": ("Londres", 1889), "Manchester City": ("Manchester", 1880),
    "Manchester United": ("Manchester", 1878), "Liverpool": ("Liverpool", 1892), "Everton": ("Liverpool", 1878), "Aston Villa": ("Birmingham", None),
    "Newcastle United": ("Newcastle", None), "Nottingham Forest": ("Nottingham", None), "AFC Bournemouth": ("Bournemouth", None),
    "Brighton & Hove Albion": ("Brighton", None), "Wolverhampton Wanderers": ("Wolverhampton", None), "Leeds United": ("Leeds", None),
    "Burnley": ("Burnley", None), "Sunderland": ("Sunderland", None), "Leicester City": ("Leicester", None), "Southampton": ("Southampton", None),
    "Ipswich Town": ("Ipswich", None), "Sheffield United": ("Sheffield", 1889), "Sheffield Wednesday": ("Sheffield", 1867), "Luton Town": ("Luton", None),
    # Espagne
    "Real Madrid": ("Madrid", 1902), "Atletico Madrid": ("Madrid", 1903), "Rayo Vallecano": ("Vallecas", None), "Getafe": ("Getafe", None),
    "Barcelona": ("Barcelone", 1899), "Espanyol": ("Barcelone", 1900), "Sevilla": ("Séville", 1890), "Real Betis": ("Séville", 1907),
    "Athletic Club": ("Bilbao", None), "Real Sociedad": ("Saint-Sébastien", None), "Villarreal": ("Villarreal", None), "Valencia": ("Valence", 1919),
    "Levante": ("Valence", 1909), "Celta Vigo": ("Vigo", None), "Deportivo Alaves": ("Vitoria", None), "Osasuna": ("Pampelune", None),
    "Mallorca": ("Majorque", None), "Girona": ("Gérone", None), "Real Oviedo": ("Oviedo", None), "Elche": ("Elche", None), "Las Palmas": ("Las Palmas", None),
    "Leganes": ("Leganés", None), "Real Valladolid": ("Valladolid", None), "Cadiz": ("Cadix", None), "Granada": ("Grenade", None), "Almeria": ("Almería", None),
    # Italie
    "Inter": ("Milan", 1908), "Milan": ("Milan", 1899), "Juventus": ("Turin", 1897), "Torino": ("Turin", 1906), "Roma": ("Rome", 1927), "Lazio": ("Rome", 1900),
    "Napoli": ("Naples", None), "Atalanta": ("Bergame", None), "Fiorentina": ("Florence", None), "Bologna": ("Bologne", None), "Genoa": ("Gênes", 1893),
    "Sampdoria": ("Gênes", 1946), "Udinese": ("Udine", None), "Cagliari": ("Cagliari", None), "Parma": ("Parme", None), "Como": ("Côme", None),
    "Hellas Verona": ("Vérone", None), "Lecce": ("Lecce", None), "Sassuolo": ("Sassuolo", None), "Pisa": ("Pise", None), "Cremonese": ("Crémone", None),
    "Empoli": ("Empoli", None), "Monza": ("Monza", None), "Venezia": ("Venise", None), "Salernitana": ("Salerne", None), "Frosinone": ("Frosinone", None),
    # Allemagne
    "Bayern München": ("Munich", None), "Borussia Dortmund": ("Dortmund", None), "Bayer Leverkusen": ("Leverkusen", None), "RB Leipzig": ("Leipzig", None),
    "Eintracht Frankfurt": ("Francfort", None), "VfB Stuttgart": ("Stuttgart", None), "Borussia Mönchengladbach": ("Mönchengladbach", None),
    "Freiburg": ("Fribourg", None), "Wolfsburg": ("Wolfsburg", None), "Mainz 05": ("Mayence", None), "Augsburg": ("Augsbourg", None),
    "Werder Bremen": ("Brême", None), "Hoffenheim": ("Hoffenheim", None), "Union Berlin": ("Berlin", 1966), "Hertha Berlin": ("Berlin", 1892),
    "1. FC Köln": ("Cologne", None), "Hamburger SV": ("Hambourg", 1887), "St. Pauli": ("Hambourg", 1910), "FC Heidenheim": ("Heidenheim", None),
    "VfL Bochum": ("Bochum", None), "Holstein Kiel": ("Kiel", None), "Darmstadt": ("Darmstadt", None), "Schalke 04": ("Gelsenkirchen", None),
    # France
    "Paris Saint-Germain": ("Paris", 1970), "Paris FC": ("Paris", 1969), "Marseille": ("Marseille", None), "Lyon": ("Lyon", None), "Monaco": ("Monaco", None),
    "Lille": ("Lille", None), "Nice": ("Nice", None), "Lens": ("Lens", None), "Rennes": ("Rennes", None), "Strasbourg": ("Strasbourg", None),
    "Toulouse": ("Toulouse", None), "Nantes": ("Nantes", None), "Brest": ("Brest", None), "Auxerre": ("Auxerre", None), "Angers": ("Angers", None),
    "Le Havre": ("Le Havre", None), "Lorient": ("Lorient", None), "Metz": ("Metz", None), "Montpellier": ("Montpellier", None), "Reims": ("Reims", None),
    "Saint-Étienne": ("Saint-Étienne", None), "Saint-Etienne": ("Saint-Étienne", None), "Clermont Foot": ("Clermont", None),
    # Pays-Bas, Portugal, Turquie, Belgique
    "Ajax": ("Amsterdam", None), "PSV Eindhoven": ("Eindhoven", None), "Feyenoord": ("Rotterdam", 1908), "Sparta Rotterdam": ("Rotterdam", 1888),
    "AZ Alkmaar": ("Alkmaar", None), "FC Twente": ("Enschede", None), "FC Utrecht": ("Utrecht", None), "Go Ahead Eagles": ("Deventer", None),
    "NEC Nijmegen": ("Nimègue", None), "Fortuna Sittard": ("Sittard", None), "Heerenveen": ("Heerenveen", None), "FC Groningen": ("Groningue", None),
    "Benfica": ("Lisbonne", 1904), "Sporting CP": ("Lisbonne", 1906), "Porto": ("Porto", 1893), "Braga": ("Braga", None), "Vitoria de Guimaraes": ("Guimarães", None),
    "Galatasaray": ("Istanbul", 1905), "Fenerbahce": ("Istanbul", 1907), "Besiktas": ("Istanbul", 1903), "Trabzonspor": ("Trabzon", None),
    "Basaksehir": ("Istanbul", 1990), "Club Brugge": ("Bruges", 1891), "Cercle Brugge": ("Bruges", 1899), "Anderlecht": ("Bruxelles", 1908),
    "Union St.Gilloise": ("Bruxelles", 1897), "Genk": ("Genk", None), "Antwerp": ("Anvers", None), "Gent": ("Gand", None), "Standard Liege": ("Liège", None),
    # Les invités d'Europe
    "Celtic": ("Glasgow", 1887), "Rangers": ("Glasgow", 1872), "Olympiacos": ("Le Pirée", None), "Panathinaikos": ("Athènes", 1908), "AEK Athens": ("Athènes", 1924),
    "PAOK": ("Thessalonique", None), "Bodø/Glimt": ("Bodø", None), "FC København": ("Copenhague", 1992), "Slavia Prague": ("Prague", 1892), "Sparta Prague": ("Prague", 1893),
    "Kairat Almaty": ("Almaty", None), "Pafos FC": ("Paphos", None), "Qarabag FK": ("Agdam", None), "Red Bull Salzburg": ("Salzbourg", None),
    "Sturm Graz": ("Graz", None), "Young Boys": ("Berne", None), "Basel": ("Bâle", None), "Dinamo Zagreb": ("Zagreb", None), "Shakhtar Donetsk": ("Donetsk", None),
    "Dynamo Kyiv": ("Kyiv", None), "Ferencvaros": ("Budapest", None), "Legia Warsaw": ("Varsovie", None), "Rapid Vienna": ("Vienne", None),
    "Crvena Zvezda": ("Belgrade", 1945), "Partizan": ("Belgrade", 1945), "Ludogorets": ("Razgrad", None), "Molde": ("Molde", None),
    "Malmö FF": ("Malmö", None), "Brøndby": ("Brøndby", None), "Midtjylland": ("Herning", None), "Lech Poznan": ("Poznań", None),
}
PREFIXES = ("1. FC ", "FC ", "AFC ", "SV ", "VfB ", "VfL ", "RB ", "Real ", "CD ", "UD ", "SC ", "AC ", "AS ", "US ", "SS ", "Club ", "Deportivo ", "Athletic ", "Sporting ", "Olympique ", "Stade ", "Racing ")
SUFFIXES = (" FC", " CF", " SC", " United", " City", " Town", " Hotspur", " Wanderers", " Albion", " Rovers", " Athletic", " Eagles", " 05", " 04", " CP", " SV", " BK", " IF", " FK")


def nom_club(team_id: int, nom_reel: str) -> str:
    """Le nom fictif d'un club : sa ville, et son année de fondation si la ville a
    plusieurs clubs ; un club inconnu de la table garde son mot principal."""
    v = VILLES.get(nom_reel)
    if v:
        ville, annee = v
        return f"{ville} {annee}" if annee else ville
    nom = nom_reel
    for p in PREFIXES:
        if nom.startswith(p):
            nom = nom[len(p):]
    for s in SUFFIXES:
        if nom.endswith(s):
            nom = nom[:-len(s)]
    nom = re.sub(r"\s+\d{2,4}$", "", nom).strip()
    return nom or nom_reel


# --------------------------------------------------------------------------
# Les compétitions : le pays (le français en base, l'écran traduit par la clé)
# --------------------------------------------------------------------------
COMPETITIONS_FICTIVES = {
    47: ("Championnat d'Angleterre", "angleterre"), 87: ("Championnat d'Espagne", "espagne"), 55: ("Championnat d'Italie", "italie"),
    54: ("Championnat d'Allemagne", "allemagne"), 53: ("Championnat de France", "france"), 57: ("Championnat des Pays-Bas", "pays_bas"),
    61: ("Championnat du Portugal", "portugal"), 71: ("Championnat de Turquie", "turquie"), 42: ("Coupe d'Europe", "europe"),
    73: ("Coupe d'Europe B", "europe_b"), 10216: ("Coupe d'Europe C", "europe_c"),
}
# la clé du mode solo (jeu/solo.COMPETITIONS) → la clé de traduction
CLES_SOLO = {"premier": "angleterre", "liga": "espagne", "seriea": "italie", "bundes": "allemagne", "ligue1": "france",
             "eredivisie": "pays_bas", "portugal": "portugal", "turquie": "turquie", "ldc": "europe", "europa": "europe_b", "conference": "europe_c"}


def nom_competition(competition_id: int, nom_reel: str) -> str:
    v = COMPETITIONS_FICTIVES.get(int(competition_id))
    if v:
        return v[0]
    if "cup" in nom_reel.lower() or "coupe" in nom_reel.lower():
        return "Coupe nationale"
    return "Championnat"


# --------------------------------------------------------------------------
# Les mods, chez le joueur
# --------------------------------------------------------------------------
def _lire_csv(chemin: pathlib.Path) -> list[list[str]]:
    if not chemin.exists():
        return []
    with open(chemin, encoding="utf-8", newline="") as f:
        lignes = [l for l in csv.reader(f) if l and not l[0].startswith("#")]
    # une première ligne d'en-tête (player_id,nom) est sautée
    if lignes and not lignes[0][0].strip().lstrip("-").isdigit():
        lignes = lignes[1:]
    return lignes


def mods(dossier: pathlib.Path | None = None) -> dict:
    """Ce que le dossier de mods contient : {"noms": {pid: nom}, "clubs": {tid: (nom, couleur|None)},
    "competitions": {cid: nom}, "portraits": dossier|None, "logos": dossier|None}."""
    d = dossier or MODS
    noms = {int(l[0]): l[1].strip() for l in _lire_csv(d / "noms.csv") if len(l) >= 2 and l[1].strip()}
    clubs = {int(l[0]): (l[1].strip(), (l[2].strip() if len(l) > 2 and l[2].strip() else None)) for l in _lire_csv(d / "clubs.csv") if len(l) >= 2 and l[1].strip()}
    comps = {int(l[0]): l[1].strip() for l in _lire_csv(d / "competitions.csv") if len(l) >= 2 and l[1].strip()}
    return {"noms": noms, "clubs": clubs, "competitions": comps,
            "portraits": (d / "portraits") if (d / "portraits").is_dir() else None,
            "logos": (d / "logos") if (d / "logos").is_dir() else None}


# --------------------------------------------------------------------------
# Appliquer un monde à une base
# --------------------------------------------------------------------------
def monde(jeu, saison: str) -> str:
    """« reel » ou « fictif » : le monde de cette base (parametre.monde)."""
    row = jeu.execute("SELECT valeur FROM parametre WHERE saison=? AND cle='monde'", (saison,)).fetchone()
    if not row:
        return "reel"
    v = row[0].strip('"')
    return "fictif" if v == "fictif" else "reel"


def _colonne(jeu, table: str, colonne: str):
    cols = [r[1] for r in jeu.execute(f"PRAGMA table_info({table})")]
    if colonne not in cols:
        jeu.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} TEXT")


def appliquer(jeu, saison: str, mode: str, dossier_mods: pathlib.Path | None = None) -> dict:
    """Écrit les noms du monde demandé dans la base (joueur.nom, club.nom,
    competition.nom), en gardant les vrais dans `nom_reel` ; « fictif » lit
    ensuite les mods s'il y en a.  Rend le compte de ce qui a changé."""
    assert mode in ("reel", "fictif")
    for table in ("joueur", "club", "competition"):
        _colonne(jeu, table, "nom_reel")
        _colonne(jeu, table, "nom_fictif")
    # les vrais noms sont gardés une fois pour toutes (la première application)
    for table in ("joueur", "club", "competition"):
        jeu.execute(f"UPDATE {table} SET nom_reel = nom WHERE nom_reel IS NULL")
    compte = {"joueurs": 0, "clubs": 0, "competitions": 0, "mods": 0}
    if mode == "reel":
        jeu.execute("UPDATE joueur SET nom = nom_reel, nom_normalise = ? WHERE nom_reel IS NOT NULL", ("",))
        for pid, nom in [tuple(r) for r in jeu.execute("SELECT player_id, nom FROM joueur")]:
            jeu.execute("UPDATE joueur SET nom_normalise=? WHERE player_id=?", (normaliser(nom), pid))
        jeu.execute("UPDATE club SET nom = nom_reel WHERE nom_reel IS NOT NULL")
        jeu.execute("UPDATE competition SET nom = nom_reel WHERE nom_reel IS NOT NULL")
    else:
        m = mods(dossier_mods)
        # jamais un vrai nom de la base, jamais deux cartes du même nom : on retire avec
        # un sel dans ces cas rares (une carte garde donc son nom d'une base à l'autre,
        # sauf si l'autre base a un vrai joueur de ce nom-là)
        reels = {normaliser(r[0]) for r in jeu.execute("SELECT nom_reel FROM joueur")}
        pris: set[str] = set()
        for pid, pays, nom_reel in [tuple(r) for r in jeu.execute("SELECT player_id, pays, nom_reel FROM joueur ORDER BY player_id")]:
            fictif = nom_joueur(pid, pays)
            if normaliser(fictif) in reels or normaliser(fictif) in pris:
                for sel in range(1, 50):
                    fictif = nom_joueur(pid, pays, sel=sel)
                    if normaliser(fictif) not in reels and normaliser(fictif) not in pris:
                        break
            pris.add(normaliser(fictif))
            nom = m["noms"].get(pid) or fictif
            if pid in m["noms"]:
                compte["mods"] += 1
            jeu.execute("UPDATE joueur SET nom=?, nom_fictif=?, nom_normalise=? WHERE player_id=?", (nom, fictif, normaliser(nom), pid))
            compte["joueurs"] += 1
        for tid, nom_reel in [tuple(r) for r in jeu.execute("SELECT team_id, nom_reel FROM club")]:
            fictif = nom_club(tid, nom_reel)
            if tid in m["clubs"]:
                nom, couleur = m["clubs"][tid]
                compte["mods"] += 1
                if couleur:
                    jeu.execute("UPDATE club SET couleur=? WHERE team_id=?", (couleur, tid))
            else:
                nom = fictif
            jeu.execute("UPDATE club SET nom=?, nom_fictif=? WHERE team_id=?", (nom, fictif, tid))
            compte["clubs"] += 1
        for cid, nom_reel in [tuple(r) for r in jeu.execute("SELECT competition_id, nom_reel FROM competition")]:
            fictif = nom_competition(cid, nom_reel)
            nom = m["competitions"].get(cid) or fictif
            jeu.execute("UPDATE competition SET nom=?, nom_fictif=? WHERE competition_id=?", (nom, fictif, cid))
            compte["competitions"] += 1
    jeu.execute("INSERT INTO parametre(saison, cle, valeur) VALUES (?, 'monde', ?) ON CONFLICT(saison, cle) DO UPDATE SET valeur=excluded.valeur",
                (saison, f'"{mode}"'))
    jeu.commit()
    return compte


def main(argv=None):
    import argparse
    import sqlite3
    ap = argparse.ArgumentParser(description="Le monde du jeu : réel ou fictif (noms générés, clubs par ville, mods).")
    ap.add_argument("--jeu", default=str(RACINE / "jeu" / "jeu_2526.sqlite"))
    ap.add_argument("--saison", default="2025/26")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--fictif", action="store_true", help="noms générés, clubs par ville, puis les mods de mods/")
    g.add_argument("--reel", action="store_true", help="les vrais noms, tels qu'importés")
    g.add_argument("--etat", action="store_true", help="dire le monde de la base")
    ap.add_argument("--mods", default=None, help="un autre dossier de mods que mods/")
    a = ap.parse_args(argv)
    jeu = sqlite3.connect(a.jeu)
    if a.etat:
        print(monde(jeu, a.saison))
        return 0
    c = appliquer(jeu, a.saison, "fictif" if a.fictif else "reel", pathlib.Path(a.mods) if a.mods else None)
    print(("monde fictif" if a.fictif else "monde réel") + f" : {c['joueurs']} joueurs, {c['clubs']} clubs, {c['competitions']} compétitions"
          + (f", {c['mods']} lignes de mods" if c["mods"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
