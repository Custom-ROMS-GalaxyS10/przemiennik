function searchRepeaters() {

    const input = document
        .getElementById("search")
        .value
        .toLowerCase();

    const repeaters = document
        .querySelectorAll(".repeater-card");

    repeaters.forEach(function(repeater) {

        const text = repeater
            .innerText
            .toLowerCase();

        if (text.includes(input)) {
            repeater.style.display = "";
        } else {
            repeater.style.display = "none";
        }
    });
}
