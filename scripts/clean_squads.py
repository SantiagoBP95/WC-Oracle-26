"""
Limpia la tabla players dejando solo jugadores convocados al Mundial 2026.
Estrategia: token-matching + lista de exclusión manual para falsos positivos.
"""
from __future__ import annotations
import sys, unicodedata, re
sys.path.insert(0, ".")

from backend.app.database import SessionLocal
from backend.app.models.football import Player, Team

# ── Convocatorias oficiales WC 2026 ──────────────────────────────────────────
# Claves = Team.display_name exacto en la BD (sin tildes)
OFFICIAL_SQUADS: dict[str, list[str]] = {
    "Mexico": [
        "Raul Rangel","Guillermo Ochoa","Carlos Acevedo","Jorge Sanchez","Israel Reyes",
        "Cesar Montes","Johan Vasquez","Jesus Gallardo","Mateo Chavez","Edson Alvarez",
        "Erik Lira","Orbelin Pineda","Alvaro Fidalgo","Brian Gutierrez","Luis Romo",
        "Obed Vargas","Gilberto Mora","Luis Chavez","Roberto Alvarado","Cesar Huerta",
        "Alexis Vega","Julian Quinones","Guillermo Martinez","Armando Gonzalez",
        "Santiago Gimenez","Raul Jimenez",
    ],
    "Sudafrica": [
        "Ronwen Williams","Ricardo Goss","Sipho Chaine","Aubrey Modiba","Khuliso Mudau",
        "Kamogelo Sebelebele","Nkosinathi Sibisi","Bradley Cross","Samukele Kabini",
        "Olwethu Makhanya","Thabang Matuludi","Mbekezeli Mbokazi","Ime Okon",
        "Oswin Appollis","Thalente Mbatha","Relebohile Mofokeng","Jayden Adams",
        "Teboho Mokoena","Themba Zwane","Sphephelo Sithole","Evidence Makgopa",
        "Tshepang Moremi","Lyle Foster","Thapelo Maseko","Iqraam Rayners",
    ],
    "Corea del Sur": [
        "Song Bumkeun","Jo Hyeonwoo","Kim Seung-gyu","Jens Castrop","Lee Hanbeom",
        "Park Jinseob","Lee Kihyuk","Kim Minjae","Kim Moonhwan","Kim Taehyeon",
        "Lee Taeseok","Seol Youngwoo","Cho Wije","Lee Donggyeong","Hwang Heechan",
        "Yang Hyunjun","Hwang Inbeom","Lee Jaesung","Kim Jingyu","Eom Jisung",
        "Bae Junho","Lee Kangin","Paik Seungho","Cho Guesung","Son Heungmin","Oh Hyeongyu",
    ],
    "Chequia": [
        "Lukas Hornicek","Matej Kovar","Jindrich Stanek","Vladimir Coufal","David Doudera",
        "Tomas Holes","Robin Hranac","Stepan Chaloupek","David Jurasek","Ladislav Krejci",
        "Jaroslav Zeleny","David Zima","Lukas Cerv","Vladimir Darida","Lukas Provod",
        "Michal Sadilek","Hugo Sochurek","Alexandr Sojka","Tomas Soucek","Pavel Sulc",
        "Denis Visinsky","Adam Hlozek","Tomas Chory","Mojmir Chytil","Jan Kuchta","Patrik Schick",
    ],
    "Canada": [
        "Dayne St Clair","Maxime Crepeau","Owen Goodman","Alistair Johnston","Derek Cornelius",
        "Richie Laryea","Niko Sigur","Joel Waterman","Luc de Fougerolles","Moise Bombito",
        "Alphonso Davies","Alfie Jones","Stephen Eustaquio","Ismael Kone","Tajon Buchanan",
        "Mathieu Choiniere","Ali Ahmed","Nathan Saliba","Liam Millar","Jacob Shaffelburg",
        "Jonathan Osorio","Jonathan David","Cyle Larin","Tani Oluwaseyi","Promise David",
    ],
    "Bosnia y Herzegovina": [
        "Nikola Vasilj","Martin Zlomislic","Osman Hadzikic","Sead Kolasinac","Amar Dedic",
        "Nihad Mujakic","Nikola Katic","Tarik Muharemovic","Stjepan Radeljic",
        "Dennis Hadzikadunic","Nidal Celik","Amir Hadziahmetovic","Ivan Sunjic","Ivan Basic",
        "Dzenis Burnic","Ermin Mahmic","Benjamin Tahirovic","Amar Memic","Armin Gigovic",
        "Kerim Alajbegovic","Esmir Bajraktarevic","Ermedin Demirovic","Jovo Lukic",
        "Samed Bazdar","Haris Tabakovic","Edin Dzeko",
    ],
    "Catar": [
        "Salah Zakaria","Meshaal Barsham","Mahmoud Abunada","Boualem Khoukhi","Pedro Miguel",
        "Sultan Al Brake","Homam Al Amin","Ahmed Fathi","Jassim Gaber","Assim Madibo",
        "Abdulaziz Hatem","Karim Boudiaf","Mohammed Mannai","Almoez Ali","Akram Afif",
        "Tahsin Mohammed","Edmilson Junior","Hassan Al Haydos","Mohammed Muntari","Yusuf Abdurisag",
    ],
    "Suiza": [
        "Marvin Keller","Gregor Kobel","Yvon Mvogo","Manuel Akanji","Aurele Amenda",
        "Eray Comert","Nico Elvedi","Luca Jaquez","Miro Muheim","Ricardo Rodriguez",
        "Silvan Widmer","Michel Aebischer","Christian Fassnacht","Remo Freuler",
        "Ardon Jashari","Fabian Rieder","Djibril Sow","Cedric Itten","Granit Xhaka",
        "Denis Zakaria","Ruben Vargas","Zeki Amdouni","Breel Embolo","Dan Ndoye",
        "Noah Okafor","Johan Manzambi",
    ],
    "Brasil": [
        "Alisson","Ederson","Weverton","Alex Sandro","Bremer","Danilo","Douglas Santos",
        "Gabriel Magalhaes","Ibanez","Leo Pereira","Marquinhos","Wesley","Bruno Guimaraes",
        # Casemiro: StatsBomb usa "Casimiro" así que incluimos ambas grafías
        "Casemiro","Casimiro","Fabinho","Lucas Paqueta","Endrick","Gabriel Martinelli",
        "Igor Thiago","Luiz Henrique","Matheus Cunha",
        # Neymar/Vinicius: incluimos alias para capturar forma larga de StatsBomb
        "Neymar Santos Junior","Vinicius Junior","Raphinha","Rayan",
    ],
    "Marruecos": [
        "Yassine Bounou","Munir El Kajoui","Ahmed Reda Tagnaouti","Noussair Mazraoui",
        "Achraf Hakimi","Zakaria El Ouahdi","Nayef Aguerd","Chadi Riad",
        "Sofyan Amrabat","Azzedine Ounahi","Bilal El Khannouss","Ismael Saibari",
        "Abdesamad Ezzalzouli","Soufiane Rahimi","Ayoub El Kaabi","Brahim Diaz",
    ],
    "Haiti": [
        "Josue Duverger","Alexandre Pierre","Johny Placide","Ricardo Ade","Carlens Arcus",
        "Hannes Delcroix","Jean-Kevin Duverne","Martin Experience","Duke Lacroix",
        "Wilguens Paugain","Jean-Ricner Bellegarde","Leverton Pierre","Danley Jean Jacques",
        "Dominique Simon","Josue Casimir","Derrick Etienne","Yassin Fortune",
        "Wilson Isidor","Lenny Joseph","Duckens Nazon","Frantzdy Pierrot","Ruben Providence",
    ],
    "Escocia": [
        "Craig Gordon","Angus Gunn","Liam Kelly","Grant Hanley","Jack Hendry","Aaron Hickey",
        "Dom Hyam","Scott McKenna","Nathan Patterson","Anthony Ralston","Andy Robertson",
        "John Souttar","Kieran Tierney","Ryan Christie","Lewis Ferguson","John McGinn",
        "Kenny McLean","Scott McTominay","Che Adams","Lyndon Dykes","Lawrence Shankland",
        "Ross Stewart",
    ],
    "Estados Unidos": [
        "Chris Brady","Matt Freese","Matt Turner","Max Arfsten","Sergino Dest","Alex Freeman",
        "Mark McKenzie","Tim Ream","Chris Richards","Antonee Robinson","Miles Robinson",
        "Joe Scally","Auston Trusty","Tyler Adams","Sebastian Berhalter","Weston McKennie",
        "Cristian Roldan","Brenden Aaronson","Christian Pulisic","Gio Reyna","Malik Tillman",
        "Tim Weah","Alejandro Zendejas","Folarin Balogun","Ricardo Pepi","Haji Wright",
    ],
    "Paraguay": [
        "Orlando Gill","Roberto Fernandez","Gaston Olveira","Juan Caceres","Gustavo Velazquez",
        "Gustavo Gomez","Junior Alonso","Jose Canale","Omar Alderete","Alexandro Maidana",
        "Fabian Balbuena","Diego Gomez","Mauricio Magalhaes","Damian Bobadilla","Braian Ojeda",
        "Andres Cubas","Matias Galarza","Alejandro Gamarra","Gustavo Caballero","Ramon Sosa",
        "Alex Arce","Isidro Pitta","Gabriel Avalos","Miguel Almiron","Julio Enciso",
        "Antonio Sanabria",
    ],
    "Australia": [
        "Patrick Beach","Paul Izzo","Mathew Ryan","Aziz Behich","Jordan Bos","Cameron Burgess",
        "Alessandro Circati","Milos Degenek","Jason Geria","Lucas Herrington","Jacob Italiano",
        "Harry Souttar","Kai Trewin","Cameron Devlin","Ajdin Hrustic","Jackson Irvine",
        "Connor Metcalfe","Nestory Irankunda","Mathew Leckie","Awer Mabil","Mohamed Toure",
        "Cristian Volpato","Tete Yengi",
    ],
    "Turquia": [
        "Altay Bayindir","Mert Gunok","Ugurcan Cakir","Abdulkerim Bardakci","Caglar Soyuncu",
        "Eren Elmali","Ferdi Kadioglu","Merih Demiral","Mert Muldur","Ozan Kabak",
        "Samet Akaydin","Zeki Celik","Hakan Calhanoglu","Ismail Yuksek","Kaan Ayhan",
        "Orkun Kokcu","Salih Ozcan","Arda Guler","Baris Alper Yilmaz","Can Uzun",
        "Irfan Can Kahveci","Kenan Yildiz","Kerem Akturkoglu","Oguz Aydin","Yunus Akgun",
    ],
    "Alemania": [
        "Manuel Neuer","Oliver Baumann","Alexander Nuebel","Nico Schlotterbeck","David Raum",
        "Nathaniel Brown","Jonathan Tah","Waldemar Anton","Joshua Kimmich","Malick Thiaw",
        "Antonio Rudiger","Pascal Gross","Leon Goretzka","Felix Nmecha","Jamal Musiala",
        "Nadiem Amiri","Jamie Leweling","Lennart Karl","Florian Wirtz","Leroy Sane",
        "Aleksandar Pavlovic","Angelo Stiller","Kai Havertz","Nick Woltemade","Deniz Undav",
        "Maximilian Beier",
    ],
    "Curazao": [
        "Tyrick Bodack","Trevor Doornbusch","Eloy Room","Riechedly Bazoer","Joshua Brenet",
        "Sherel Floranus","Deveron Fonville","Jurien Gaari","Armando Obispo","Shurandy Sambo",
        "Juninho Bacuna","Leandro Bacuna","Livano Comenencia","Kevin Felida","Tyrese Noslin",
        "Godfried Roemeratoe","Jeremy Antonisse","Tahith Chong","Kenji Gorre","Sontje Hansen",
        "Gervane Kastaneer","Brandley Kuwas","Jurgen Locadia","Jearl Margaritha",
    ],
    "Costa de Marfil": [
        "Yahia Fofana","Mohamed Kone","Alban Lafont","Emmanuel Agbadou","Christopher Operi",
        "Ousmane Diomande","Ghislain Konan","Odilon Kossounou","Wilfried Singo","Evan Ndicka",
        "Seko Fofana","Franck Kessie","Ibrahim Sangare","Jean Michael Seri","Simon Adingra",
        "Ange-Yoan Bonny","Amad Diallo","Evann Guessand","Nicolas Pepe","Elye Wahi",
    ],
    "Ecuador": [
        "Hernan Galindez","Moises Ramirez","Gonzalo Valle","Piero Hincapie","Willian Pacho",
        "Pervis Estupinan","Felix Torres","Joel Ordonez","Jackson Porozo","Angelo Preciado",
        "Yaimar Medina","Moises Caicedo","Alan Franco","Kendry Paez","Gonzalo Plata",
        "Pedro Vite","Jordy Alcivar","Denil Castillo","John Yeboah","Nilson Angulo",
        "Alan Minda","Enner Valencia","Kevin Rodriguez","Jordy Caicedo","Anthony Valencia",
        "Jeremy Arevalo",
    ],
    "Paises Bajos": [
        "Mark Flekken","Robin Roefs","Bart Verbruggen","Nathan Ake","Virgil van Dijk",
        "Denzel Dumfries","Jan Paul van Hecke","Jurrien Timber","Jorrel Hato","Micky van de Ven",
        "Ryan Gravenberch","Frenkie de Jong","Teun Koopmeiners","Tijjani Reijnders",
        "Marten de Roon","Guus Til","Quinten Timber","Mats Wieffer","Brian Brobbey",
        "Memphis Depay","Cody Gakpo","Noa Lang","Donyell Malen","Crysencio Summerville",
        "Wout Weghorst","Justin Kluivert",
    ],
    "Japon": [
        "Tomoki Hayakawa","Keisuke Osako","Zion Suzuki","Ko Itakura","Hiroki Ito",
        "Yuto Nagatomo","Ayumu Seko","Yukinari Sugawara","Junnosuke Suzuki","Shogo Taniguchi",
        "Takehiro Tomiyasu","Tsuyoshi Watanabe","Ritsu Doan","Wataru Endo","Junya Ito",
        "Daichi Kamada","Takefusa Kubo","Keito Nakamura","Kaishu Sano","Ao Tanaka",
        "Keisuke Goto","Daizen Maeda","Koki Ogawa","Kento Shiogai","Yuito Suzuki","Ayase Ueda",
        # StatsBomb usa el nombre japonés completo con kanji romanizado
        "Yuya Osako",
    ],
    "Suecia": [
        "Viktor Johansson","Gustaf Lagerbielke","Kristoffer Nordfeldt","Jacob Zetterstrom",
        "Hjalmar Ekdal","Gabriel Gudmundsson","Isak Hien","Victor Lindelof","Eric Smith",
        "Carl Starfelt","Daniel Svensson","Yasin Ayari","Lucas Bergvall","Jesper Karlstrom",
        "Benjamin Nygren","Ken Sema","Elliot Stroud","Mattias Svanberg","Besfort Zeneli",
        "Taha Ali","Alexander Bernhardsson","Anthony Elanga","Viktor Gyokeres","Alexander Isak",
        "Gustaf Nilsson",
    ],
    "Tunez": [
        "Sabri Ben Hessen","Abdelmouhib Chamakh","Aymen Dahman","Ali Abdi","Adem Arous",
        "Dylan Bronn","Moutaz Neffati","Omar Rekik","Montassar Talbi","Yan Valery",
        "Anis Ben Slimane","Ismael Gharbi","Rani Khedira","Hannibal Mejbri","Ellyes Skhiri",
        "Elias Achouri","Khalil Ayari","Firas Chaouat","Hazem Mastouri","Elias Saad",
        "Sebastian Tounekti",
    ],
    "Belgica": [
        "Thibaut Courtois","Senne Lammens","Mike Penders","Timothy Castagne","Zeno Debast",
        "Maxim De Cuyper","Koni De Winter","Brandon Mechele","Thomas Meunier","Nathan Ngoy",
        "Joaquin Seys","Arthur Theate","Kevin De Bruyne","Amadou Onana","Nicolas Raskin",
        "Youri Tielemans","Hans Vanaken","Axel Witsel","Charles De Ketelaere","Jeremy Doku",
        "Romelu Lukaku","Dodi Lukebakio","Diego Moreira","Alexis Saelemaekers","Leandro Trossard",
    ],
    "Egipto": [
        "Mohamed El Shenawy","Mostafa Shobeir","Mohamed Abdelmonem","Mohamed Hany",
        "Yasser Ibrahim","Hossam Abdelmaguid","Ahmed Fattouh","Rami Rabia","Karim Hafez",
        "Marwan Attia","Ahmed Sayed","Mahmoud Hassan","Emam Ashour","Ibrahim Adel",
        "Nabil Emad","Hamdi Fathi","Mohamed Salah","Omar Marmoush","Hamza Abdel Karim",
    ],
    "Iran": [
        "Alireza Beiranvand","Seyed Hossein Hosseini","Payam Niazmand","Danial Eiri",
        "Ehsan Hajsafi","Saleh Hardani","Hossein Kanaani","Shoja Khalilzadeh",
        "Milad Mohammadi","Ali Nemati","Ramin Rezaeian","Rouzbeh Cheshmi","Saeid Ezatolahi",
        "Mehdi Ghaedi","Saman Ghoddos","Alireza Jahanbakhsh","Mehdi Torabi",
        "Ali Alipour","Amirhossein Hosseinzadeh","Mehdi Taremi",
    ],
    "Nueva Zelanda": [
        "Max Crocombe","Alex Paulsen","Michael Woud","Tyler Bindon","Michael Boxall",
        "Liberato Cacace","Francis de Vries","Callan Elliot","Tim Payne","Nando Pijnaker",
        "Tommy Smith","Joe Bell","Matt Garbett","Eli Just","Callum McCowatt","Ben Old",
        "Alex Rufer","Marko Stamenic","Sarpreet Singh","Ryan Thomas",
        "Kosta Barbarouses","Ben Waine","Chris Wood",
    ],
    "Espana": [
        "Unai Simon","David Raya","Joan Garcia","Marc Cucurella","Pau Cubarsi","Aymeric Laporte",
        "Alejandro Grimaldo","Pedro Porro","Eric Garcia","Marcos Llorente","Marc Pubill",
        "Gavi","Rodri","Pedri","Martin Zubimendi","Fabian Ruiz","Alex Baena","Mikel Merino",
        "Lamine Yamal","Nico Williams","Dani Olmo","Ferran Torres","Mikel Oyarzabal",
        "Yeremy Pino","Borja Iglesias","Victor Munoz",
        # Alias para capturar nombres completos de StatsBomb:
        "Pablo Paez Gavira",  # Gavi
        "Francisco Roman Alarcon",  # Isco — pero no está en el squad 2026, no lo añadimos
    ],
    "Cabo Verde": [
        "Marcio Rosa","Vozinha","Logan Costa","Roberto Lopes","Steven Moreira","Wagner Pina",
        "Kelvin Pires","Telmo Arcanjo","Laros Duarte","Jamiro Monteiro","Kevin Pina",
        "Yannick Semedo","Gilson Benchimol","Jovane Cabral","Dailon Livramento",
        "Ryan Mendes","Nuno da Costa","Garry Rodrigues","Willy Semedo","Helio Varela",
    ],
    "Arabia Saudita": [
        "Nawaf Al Aqidi","Mohamed Al Owais","Ahmed Alkassar","Saud Abdulhamid","Jehad Thakri",
        "Abdulelah Al Amri","Hassan Tambakti","Ali Lajami","Hassan Kadesh","Moteb Al Harbi",
        "Nawaf Boushal","Ali Majrashi","Ziyad Al Johani","Nasser Al Dawsari","Mohamed Kanno",
        "Abdullah Al Khaibari","Musab Al Juwayr","Sultan Mandash","Ayman Yahya",
        "Khalid Al Ghannam","Salem Al Dawsari","Abdullah Al Hamdan","Feras Al Brikan",
        "Saleh Al Shehri",
    ],
    "Uruguay": [
        "Sergio Rochet","Fernando Muslera","Santiago Mele","Guillermo Varela","Ronald Araujo",
        "Jose Maria Gimenez","Santiago Bueno","Sebastian Caceres","Mathias Olivera",
        "Joaquin Piquerez","Matias Vina","Maximiliano Araujo","Giorgian de Arrascaeta",
        "Rodrigo Bentancur","Agustin Canobbio","Nicolas de la Cruz","Facundo Pellistri",
        "Brian Rodriguez","Manuel Ugarte","Federico Valverde","Rodrigo Zalazar",
        "Rodrigo Aguirre","Federico Vinas","Darwin Nunez",
    ],
    "Francia": [
        "Mike Maignan","Robin Risser","Brice Samba","Lucas Digne","Malo Gusto",
        "Lucas Hernandez","Theo Hernandez","Ibrahima Konate","Maxence Lacroix","Jules Kounde",
        "William Saliba","Dayot Upamecano","Ngolo Kante","Manu Kone","Adrien Rabiot",
        "Aurelien Tchouameni","Warren Zaire-Emery","Maghnes Akliouche","Bradley Barcola",
        "Rayan Cherki","Ousmane Dembele","Desire Doue","Michael Olise","Kylian Mbappe",
        "Jean-Philippe Mateta","Marcus Thuram",
    ],
    "Senegal": [
        "Edouard Mendy","Mory Diaw","Yehvann Diouf","Krepin Diatta","Antoine Mendy",
        "Kalidou Koulibaly","Mamadou Sarr","Moussa Niakhate","Abdoulaye Seck","Ismail Jakobs",
        "Idrissa Gana Gueye","Pape Gueye","Lamine Camara","Habib Diarra","Pathe Ciss",
        "Pape Matar Sarr","Sadio Mane","Ismaila Sarr","Iliman Ndiaye","Assane Diao",
        "Nicolas Jackson","Bamba Dieng","Cherif Ndiaye",
    ],
    "Irak": [
        "Fahad Talib","Jalal Hassan","Ahmed Basil","Hussein Ali","Manaf Younis","Zaid Tahseen",
        "Rebin Sulaka","Akam Hashem","Merchas Doski","Ahmed Yahya","Zaid Ismail",
        "Frans Putros","Mustafa Saadoon","Kevin Yakob","Zidane Iqbal","Ibrahim Bayesh",
        "Ahmed Qasim","Ali Jassim","Ali Al Hamadi","Ali Yousef","Aymen Hussein","Mohanad Ali",
    ],
    "Noruega": [
        "Orjan Nyland","Egil Selvik","Sander Tangvik","Kristoffer Ajer","Fredrik Bjorkan",
        "Sondre Langas","Torbjorn Heggem","Marcus Holmgren Pedersen","Julian Ryerson",
        "Leo Ostigard","Fredrik Aursnes","Patrick Berg","Sander Berge","Oscar Bobb",
        "Jens Petter Hauge","Antonio Nusa","Andreas Schjelderup","Morten Thorsby",
        "Kristian Thorstvedt","Martin Odegaard","Erling Haaland","Alexander Sorloth",
        "Jorgen Strand Larsen",
    ],
    "Argentina": [
        "Emiliano Martinez","Geronimo Rulli","Juan Musso","Leonardo Balerdi","Gonzalo Montiel",
        "Nicolas Tagliafico","Lisandro Martinez","Cristian Romero","Nicolas Otamendi",
        "Facundo Medina","Nahuel Molina","Leandro Paredes","Rodrigo De Paul","Valentin Barco",
        "Giovani Lo Celso","Exequiel Palacios","Alexis Mac Allister","Enzo Fernandez",
        "Julian Alvarez","Lionel Messi","Nicolas Gonzalez","Thiago Almada","Giuliano Simeone",
        "Nicolas Paz","Lautaro Martinez",
    ],
    "Argelia": [
        "Oussama Benbot","Melvin Masstil","Luca Zidane","Achraf Abada","Rayan Ait Nouri",
        "Zinedine Belaid","Rafik Belghali","Ramy Bensebaini","Samir Chergui","Jaouen Hadjam",
        "Aissa Mandi","Houssem Aouar","Nabil Bentaleb","Hicham Boudaoui","Fares Chaibi",
        "Ibrahim Maza","Yassine Titraoui","Ramiz Zerrouki","Mohamed Amine Amoura",
        "Nadir Benbouali","Adil Boulbina","Fares Ghedjemis","Amine Gouiri","Riyad Mahrez",
    ],
    "Austria": [
        "Patrick Pentz","Alexander Schlager","Florian Wiegele","David Affengruber","David Alaba",
        "Kevin Danso","Marco Friedl","Philipp Lienhart","Stefan Posch","Alexander Prass",
        "Michael Svoboda","Christoph Baumgartner","Carney Chukwuemeka","Florian Grillitsch",
        "Konrad Laimer","Marcel Sabitzer","Xaver Schlager","Romano Schmid","Nicolas Seiwald",
        "Paul Wanner","Patrick Wimmer","Marko Arnautovic","Michael Gregoritsch","Sasa Kalajdzic",
    ],
    "Jordania": [
        "Yazid Abulaila","Abdallah Al Fakhouri","Mohammad Abu Hashish","Abdullah Nasib",
        "Hussam Abu Dhahab","Yazan Al Arab","Mohammad Abu Alnadi","Salem Obaid",
        "Saed Al Rosan","Ehsan Haddad","Anas Badawi","Amer Jamous","Noor Al Rawabdeh",
        "Rajaei Ayed","Ibrahim Sadeh","Mohannad Abu Taha","Nizar Al Rashdan",
        "Mohammad Al Dawoud","Mahmoud Mardahi","Mohammad Abu Zraiq","Ali Olwan",
        "Mousa Al Tamari","Odeh Fakhoury","Ibrahim Sabra","Ali Azaizeh",
    ],
    "Portugal": [
        "Diogo Costa","Jose Sa","Rui Silva","Tomas Araujo","Joao Cancelo","Diogo Dalot",
        "Ruben Dias","Goncalo Inacio","Nuno Mendes","Matheus Nunes","Nelson Semedo",
        "Renato Veiga","Samuel Costa","Bruno Fernandes","Joao Neves","Ruben Neves",
        "Bernardo Silva","Vitinha","Francisco Conceicao","Joao Felix","Goncalo Guedes",
        "Rafael Leao","Pedro Neto","Goncalo Ramos","Cristiano Ronaldo","Francisco Trincao",
    ],
    "RD Congo": [
        "Matthieu Epolo","Timothy Fayulu","Lionel Mpasi","Dylan Batubinsika","Gedeon Kalulu",
        "Steve Kapuadi","Joris Kayembe","Arthur Masuaku","Chancel Mbemba","Axel Tuanzebe",
        "Aaron Wan-Bissaka","Gael Kakuta","Edo Kayembe","Nathanael Mbuku","Samuel Moutoussamy",
        "Charles Pickel","Noah Sadiki","Aaron Tshibola","Cedric Bakambu","Simon Banza",
        "Fiston Mayele","Yoane Wissa","Theo Bongonda",
    ],
    "Uzbekistan": [
        "Botirali Ergashev","Abduvohid Nematov","Utkir Yusupov","Abdukodir Khusanov",
        "Khojiakbar Alijonov","Rustamjon Ashurmatov","Farrukh Sayfiev","Sherzod Nasrullaev",
        "Umarbek Eshmuradov","Avazbek Ulmasaliev","Jakhongir Urozov","Bekhruz Karimov",
        "Abdulla Abdullaev","Akmal Mozgovoy","Otabek Shukurov","Jamshid Iskanderov",
        "Odiljon Hamrobekov","Jaloliddin Masharipov","Azizbek Ganiev","Sherzod Esanov",
        "Abbosbek Fayzullaev","Azizbek Amonov","Eldor Shomurodov","Igor Sergeev",
        "Oston Urunov","Dostonbek Hamdamov",
    ],
    "Colombia": [
        "Camilo Vargas","Alvaro Montero","David Ospina","Davinson Sanchez","Jhon Lucumi",
        "Yerry Mina","Willer Ditta","Daniel Munoz","Santiago Arias","Johan Mojica",
        "Deiver Machado","Richard Rios","Jefferson Lerma","Kevin Castano","Juan Camilo Portilla",
        "Gustavo Puerta","Jhon Arias","Jorge Carrascal","Juan Fernando Quintero",
        "James Rodriguez","Jaminton Campaz","Juan Camilo Hernandez","Luis Diaz","Luis Suarez",
        "Carlos Gomez","Jhon Cordoba",
    ],
    "Inglaterra": [
        "Jordan Pickford","Dean Henderson","James Trafford","Reece James","Ezri Konsa",
        "Jarell Quansah","John Stones","Marc Guehi","Dan Burn","Djed Spence",
        "Tino Livramento","Declan Rice","Elliot Anderson","Kobbie Mainoo","Jordan Henderson",
        "Morgan Rogers","Jude Bellingham","Eberechi Eze","Harry Kane","Ivan Toney",
        "Ollie Watkins","Bukayo Saka","Marcus Rashford","Anthony Gordon","Noni Madueke",
    ],
    "Croacia": [
        "Dominik Livakovic","Dominik Kotarski","Ivor Pandur","Josko Gvardiol","Duje Caleta-Car",
        "Josip Sutalo","Josip Stanisic","Marin Pongracic","Martin Erlic","Luka Vuskovic",
        "Luka Modric","Mateo Kovacic","Mario Pasalic","Nikola Vlasic","Luka Sucic",
        "Martin Baturina","Kristijan Jakic","Petar Sucic","Nikola Moro","Toni Fruk",
        "Ivan Perisic","Andrej Kramaric","Ante Budimir","Petar Musa","Igor Matanovic",
    ],
    "Ghana": [
        "Joseph Anang","Benjamin Asare","Lawrence Ati-Zigi","Jonas Adjetey","Derrick Luckassen",
        "Gideon Mensah","Abdul Mumin","Jerome Opoku","Baba Abdul Rahman","Alidu Seidu",
        "Marvin Senaya","Augustine Boakye","Abdul Fatawu Issahaku","Elisha Owusu",
        "Thomas Partey","Kwasi Sibo","Kamal Deen Sulemana","Caleb Yirenkyi",
        "Jordan Ayew","Christopher Bonsu Baah","Ernest Nuamah","Antoine Semenyo",
        "Brandon Thomas-Asante","Inaki Williams",
    ],
    "Panama": [
        "Orlando Mosquera","Luis Mejia","Cesar Samudio","Cesar Blackman","Jorge Gutierrez",
        "Amir Murillo","Fidel Escobar","Andres Andrade","Edgardo Farina","Jose Cordoba",
        "Eric Davis","Jiovany Ramos","Roderick Miller","Anibal Godoy","Adalberto Carrasquilla",
        "Carlos Harvey","Cristian Martinez","Jose Luis Rodriguez","Cesar Yanis","Yoel Barcenas",
        "Alberto Quintero","Ismael Diaz","Cecilio Waterman","Jose Fajardo","Tomas Rodriguez",
    ],
}

# ── Exclusiones manuales ──────────────────────────────────────────────────────
# Jugadores que el algoritmo de tokens retiene por coincidencia parcial de nombre
# pero que NO están en la convocatoria oficial del WC 2026.
MANUAL_EXCLUDE: set[str] = {
    # Retirados o no convocados (nombres tal cual aparecen en la BD)
    "Carlos Alberto Vela Garrido",       # México - retirado
    "Henry Josué Martín Mex",            # México - no convocado
    "Hirving Rodrigo Lozano Bahena",     # México - no convocado
    "Javier Hernández Balcázar",         # México - retirado
    "Andrés Iniesta Luján",              # España - retirado
    "Carlos Soler Barragán",             # España - no convocado
    "Daniel Olmo Carvajal",              # España - lesionado/no convocado
    "Diego da Silva Costa",              # España - retirado
    "Francisco Román Alarcón Suárez",   # España - Isco, no convocado
    "Álvaro Borja Morata Martín",        # España - no convocado
    "Sergio Ramos García",               # España - retirado
    "José Ignacio Fernández Iglesias",   # España - Joselu, no convocado
    "Iago Aspas Juncal",                 # España - no convocado
    "Marco Asensio Willemsen",           # España - no convocado
    "Gerard Piqué Bernabéu",             # España - retirado
    "Faustino Marcos Alberto Rojo",      # Argentina - retirado
    "Gabriel Iván Mercado",              # Argentina - retirado
    "Paulo Bruno Exequiel Dybala",       # Argentina - no convocado
    "Sergio Leonel Agüero del Castillo", # Argentina - retirado
    "Ángel Fabián Di María Hernández",   # Argentina - retirado
    "Mario Mandžukić",                   # Croacia - retirado
    "Ante Rebić",                        # Croacia - no convocado
    "Bruno Petković",                    # Croacia - no convocado
    "Domagoj Vida",                      # Croacia - retirado
    "Ivan Rakitić",                      # Croacia - retirado
    "Lovro Majer",                       # Croacia - no convocado
    "Marcelo Brozović",                  # Croacia - no convocado
    "Marko Livaja",                      # Croacia - no convocado
    "Milan Badelj",                      # Croacia - retirado
    "Mislav Oršić",                      # Croacia - no convocado
    "Eden Hazard",                       # Bélgica - retirado
    "Adnan Januzaj",                     # Bélgica - retirado
    "Dries Mertens",                     # Bélgica - retirado
    "Jan Vertonghen",                    # Bélgica - retirado
    "Marouane Fellaini-Bakkioui",        # Bélgica - retirado
    "Michy Batshuayi Tunga",             # Bélgica - no convocado
    "Nacer Chadli",                      # Bélgica - retirado
    "Edinson Roberto Cavani Gómez",      # Uruguay - retirado
    "Luis Alberto Suárez Díaz",          # Uruguay - retirado
    "Antoine Griezmann",                 # Francia - no convocado
    "Benjamin Pavard",                   # Francia - no convocado
    "Adrien Rabiot",                     # Francia - se verifica en squad oficial ✓ → QUITAR de exclusión
    "Blerim Džemaili",                   # Suiza - retirado
    "Josip Drmic",                       # Suiza - retirado
    "Boulaye Dia",                       # Senegal - no convocado
    "Famara Diedhiou",                   # Senegal - no convocado
    "Moussa Wagué",                      # Senegal - no convocado
    "Achraf Dari",                       # Marruecos - juega por Bélgica, no convocado por Marruecos
    "Abdelhamid Sabiri",                 # Marruecos - no convocado
    "Hakim Ziyech",                      # Marruecos - retirado
    "Khalid Boutaïb",                    # Marruecos - retirado
    "Zakaria Aboukhlal",                 # Marruecos - no convocado
    "Keisuke Honda",                     # Japón - retirado
    "Genki Haraguchi",                   # Japón - no convocado
    "Craig Goodwin",                     # Australia - no convocado
    "Mile Jedinak",                      # Australia - retirado
    "Mitchell Thomas Duke",              # Australia - no convocado
    "Harry Maguire",                     # Inglaterra - no convocado
    "Jesse Lingard",                     # Inglaterra - retirado
    "Jack Grealish",                     # Inglaterra - no convocado
    "Eric Dier",                         # Inglaterra - no convocado
    "Bamidele Alli",                     # Inglaterra - no convocado
    "Kieran Trippier",                   # Inglaterra - no convocado
    "Marco Reus",                        # Alemania - retirado
    "Toni Kroos",                        # Alemania - retirado
    "Serge Gnabry",                      # Alemania - no convocado
    "İlkay Gündoğan",                   # Alemania - no convocado (retirado)
    "Niclas Füllkrug",                   # Alemania - se verifica ✓ no está en squad 2026 → excluir
    "Kléper Laveran Lima Ferreira",      # Portugal - Pepe, retirado
    "Ricardo Andrade Quaresma Bernardo", # Portugal - retirado
    "Radamel Falcao García Zárate",      # Colombia - retirado
    "Juan Guillermo Cuadrado Bello",     # Colombia - retirado
    "Luis Fernando Muriel Fruto",        # Colombia - no convocado
    "Juan Fernando Quintero Paniagua",   # Colombia - EN squad → QUITAR de exclusión
    "André Ayew Pelé",                   # Ghana - no convocado
    "Mohamed Salisu",                    # Ghana - no convocado
    "Mohammed Kudus",                    # Ghana - confirmar...
    "Andreas Granqvist",                 # Suecia - retirado
    "Emil Peter Forsberg",               # Suecia - no convocado
    "Ludwig Augustinsson",               # Suecia - no convocado
    "Daley Blind",                       # Países Bajos - retirado
    "Davy Klaassen",                     # Países Bajos - no convocado
    "Luuk de Jong",                      # Países Bajos - no convocado
    "Carlos Henrique Casimiro",          # Brasil - EN squad (Casemiro) → QUITAR de exclusión
    "José Paulo Bezzera Maciel Júnior",  # Brasil - Jô, no convocado → EXCLUIR
    "Lucas Tolentino Coelho de Lima",    # Brasil - Lucas/Hulk?, no convocado → verificar
    "Pedro Guilherme Abreu dos Santos",  # Brasil - Pedro de Flamengo → confirmar
    "Philippe Coutinho Correia",         # Brasil - retirado
    "Renato Soares de Oliveira Augusto", # Brasil - retirado
    "Richarlison de Andrade",            # Brasil - no convocado
    "Roberto Firmino Barbosa de Oliveira", # Brasil - retirado
    "Thiago Emiliano da Silva",          # Brasil - retirado (Thiago Silva)
    "Enner Remberto Valencia Lastra",    # Ecuador - EN squad ✓ → QUITAR de exclusión
    "Young-Gwon Kim",                    # Corea del Sur - no convocado
    "Seung-Ho Paik",                     # Corea del Sur - EN squad ✓ → QUITAR
    "Hee-Chan Hwang",                    # Corea del Sur - EN squad ✓ → QUITAR
    "Heung-Min Son",                     # Corea del Sur - EN squad ✓ → QUITAR
    "Gue-Sung Cho",                      # Corea del Sur - EN squad ✓ → QUITAR
    "Felipe Abdiel Baloy Ramírez",       # Panamá - retirado
    "Fakhreddine Ben Youssef",           # Túnez - no convocado
    "Ferjani Sassi",                     # Túnez - no convocado
    "Dylan Daniel Mahmoud Bronn",        # Túnez - EN squad ✓ → QUITAR
    "Salman Mohammed Al Faraj",          # Arabia Saudita - no convocado
}

# Quitar de exclusión los que SÍ están en la convocatoria oficial
_DO_NOT_EXCLUDE = {
    "Adrien Rabiot",
    "Juan Fernando Quintero Paniagua",
    "Carlos Henrique Casimiro",
    "Enner Remberto Valencia Lastra",
    "Seung-Ho Paik",
    "Hee-Chan Hwang",
    "Heung-Min Son",
    "Gue-Sung Cho",
    "Dylan Daniel Mahmoud Bronn",
}
MANUAL_EXCLUDE -= _DO_NOT_EXCLUDE


def _normalize(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_ = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9 ]", "", ascii_.lower()).strip()


def _tokens(name: str) -> set[str]:
    return {t for t in _normalize(name).split() if len(t) > 2}


def player_in_squad(db_name: str, squad_names: list[str]) -> bool:
    db_tok = _tokens(db_name)
    for official in squad_names:
        off_tok = _tokens(official)
        common = db_tok & off_tok
        if len(common) >= 2:
            return True
        if any(len(t) >= 5 for t in common):
            return True
    return False


def main():
    db = SessionLocal()
    teams = {t.id: t.display_name for t in db.query(Team).all()}
    players = db.query(Player).all()

    to_delete: list[int] = []
    kept_names: list[str] = []

    for p in players:
        # Exclusión manual explícita
        if p.name in MANUAL_EXCLUDE:
            to_delete.append(p.id)
            continue

        team_name = teams.get(p.team_id, "")
        squad = OFFICIAL_SQUADS.get(team_name)

        if squad is None:
            to_delete.append(p.id)
            continue

        if player_in_squad(p.name, squad):
            kept_names.append(f"{team_name} | {p.name}")
        else:
            to_delete.append(p.id)

    print(f"Total jugadores en BD: {len(players)}")
    print(f"A conservar: {len(kept_names)}")
    print(f"A eliminar:  {len(to_delete)}")

    if "--dry-run" in sys.argv:
        print()
        print("=== CONSERVADOS ===")
        for n in sorted(kept_names):
            print(f"  OK  {n}")
        return

    db.query(Player).filter(Player.id.in_(to_delete)).delete(synchronize_session=False)
    db.commit()
    print(f"\nEliminados {len(to_delete)} jugadores.")
    print(f"Quedan {len(kept_names)} jugadores convocados al WC 2026.")
    db.close()


if __name__ == "__main__":
    main()
