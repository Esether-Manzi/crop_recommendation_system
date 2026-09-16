console.log("Crop Recommendation System Loaded");

// Adds a show/hide eye icon to every password field on the page, so
// users can toggle plaintext visibility while typing their password.
document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll('input[type="password"]').forEach((input) => {
        if (input.closest(".password-toggle-wrap")) {
            return;
        }

        const wrapper = document.createElement("div");
        wrapper.className = "input-group password-toggle-wrap";
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);

        const toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "btn btn-outline-secondary";
        toggle.setAttribute("aria-label", "Show password");
        toggle.innerHTML = '<i class="fa-solid fa-eye"></i>';

        toggle.addEventListener("click", () => {
            const isHidden = input.type === "password";
            input.type = isHidden ? "text" : "password";
            toggle.innerHTML = isHidden
                ? '<i class="fa-solid fa-eye-slash"></i>'
                : '<i class="fa-solid fa-eye"></i>';
            toggle.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
        });

        wrapper.appendChild(toggle);
    });
});