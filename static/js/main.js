document.addEventListener("DOMContentLoaded", () => {
  // Flash message auto-dismiss
  const flashMessages = document.querySelectorAll(".flash-message")
  flashMessages.forEach((message) => {
    setTimeout(() => {
      message.style.opacity = "0"
      setTimeout(() => {
        message.style.display = "none"
      }, 500)
    }, 5000)
  })

  // Form validation
  const ticketForm = document.querySelector("form")
  if (ticketForm) {
    ticketForm.addEventListener("submit", (e) => {
      const requiredFields = ticketForm.querySelectorAll("[required]")
      let isValid = true

      requiredFields.forEach((field) => {
        if (!field.value.trim()) {
          isValid = false
          field.classList.add("error")
        } else {
          field.classList.remove("error")
        }
      })

      if (!isValid) {
        e.preventDefault()
        alert("Please fill in all required fields.")
      }
    })
  }
})
