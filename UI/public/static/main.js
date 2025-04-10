document.addEventListener("DOMContentLoaded", () => {
    const links = document.querySelectorAll("a.animated-link");
  
    // Add event listeners for the fade-out animation on link click
    links.forEach((link) => link.addEventListener("click", handleLinkClick));
  
    // Trigger fade-in when the page loads
    document.body.classList.add("fade-in");
  });
  const homeApp = Vue.createApp({
    data() {
      return {
        events: [], // Store fetched events
        loading: true, // Loading state for UI feedback
        error: null, // Error handling
        selectedEvent: {}, // Track the event to show in the modal
        showSignupModal: false, // Track visibility of the signup modal
        attendeeForms: [], // Initialize attendee forms array
        paymentReady: false, // Track payment readiness
      };
    },
    async created() {
      console.log("Vue App is created. Fetching events...");
      try {
        this.events = await fetchEvents(); // Fetch events from the API
        console.log("Events fetched:", this.events);
      } catch (error) {
        console.error("Error in created hook:", error);
        this.error = "Failed to load events. Please try again later.";
      } finally {
        this.loading = false;
      }
    },
    methods: {
      // Close the event modal
      closeEventModal() {
        this.selectedEvent = {};
      },

      formatDateTime(datetimeStr) {
        const date = new Date(datetimeStr);
        return date.toLocaleString("en-SG", {
          dateStyle: "medium",
          timeStyle: "short"
        });
      },
  
      // Add an attendee form
      addAttendeeForm() {
        const attendeeForm = {
          name: "",
          email: "",
          phone: "",
          dietaryRestrictions: "",
          specialRequests: "",
        };
        this.attendeeForms.push(attendeeForm);
      },

      async joinWaitlist(date) {
        const user = JSON.parse(sessionStorage.getItem("user"));
        if (!user) {
          const loginPrompt = new bootstrap.Modal(document.getElementById('loginPromptModalEvents'));
          loginPrompt.show();
          return;
        }
      
        const eventID = this.selectedEvent.id;
        const rawDateTime = date.eventDateTime;
        const encodedDateTime = encodeURIComponent(rawDateTime);  // ✅ Encode it properly
      
        try {
          const response = await fetch(`http://localhost:5003/waitlist/${eventID}/${encodedDateTime}`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json"
            },
            body: JSON.stringify({ userID: user.userID })
          });
      
          const result = await response.json();
      
          if (response.status === 201) {
            const msg = `You have joined the waitlist for "${this.selectedEvent.name}" on ${this.formatDateTime(rawDateTime)}`;
            document.getElementById("waitlistSuccessMessage").textContent = msg;
            const modal = new bootstrap.Modal(document.getElementById('waitlistModal'));
            modal.show();
          } else if (response.status === 409) {
            const alreadyModal = new bootstrap.Modal(document.getElementById('alreadyInWaitlistModal'));
            alreadyModal.show();
          } else {
            alert("An error occurred. Please try again.");
          }
      
        } catch (err) {
          console.error("Error joining waitlist:", err);
          alert("Something went wrong. Try again later.");
        }
      },
      

      // Remove an attendee form
      removeAttendeeForm(index) {
        if (this.attendeeForms.length > 1) {
          this.attendeeForms.splice(index, 1);
        } else {
          alert("At least one attendee is required.");
        }
      },
  
      // Open the event modal
      openEventModal(event) {
        this.selectedEvent = {
          ...event,
          date: event.date, // Use the formatted date from the API
        };
        this.showSignupModal = false; // Ensure the signup modal is closed
      },
  
      // Open the signup modal
      openSignupModal() {
        this.showSignupModal = true;
  
        // Ensure at least one attendee form is available
        if (this.attendeeForms.length === 0) {
          this.addAttendeeForm();
        }
  
        // Manually show the signup modal using Bootstrap's JavaScript API
        this.$nextTick(() => {
          const signupModalInstance = new bootstrap.Modal(
            document.getElementById("signupModal")
          );
          signupModalInstance.show();
        });
      },
  
      // Close the signup modal
      closeSignupModal() {
        this.showSignupModal = false;
        this.attendeeForms = [
          {
            name: "",
            email: "",
            phone: "",
            dietaryRestrictions: "",
            specialRequests: "",
          },
        ];
  
        const signupModalInstance = bootstrap.Modal.getInstance(
          document.getElementById("signupModal")
        );
        if (signupModalInstance) {
          signupModalInstance.hide();
        }
  
        this.paymentReady = false;
      },
  
      // Toggle payment readiness
      togglePaymentReady() {
        this.paymentReady = !this.paymentReady;
      },
  
      // Submit registration logic (placeholder)
      submitRegistration() {
        console.log("Submitting registration...");
        console.log("Selected Event:", this.selectedEvent);
        console.log("Attendee Forms:", this.attendeeForms);
  
        // Simulate success
        const successModalInstance = new bootstrap.Modal(
          document.getElementById("successModal")
        );
        successModalInstance.show();
  
        // Reset forms after submission
        this.closeSignupModal();
      },
  
      // Add event to Google Calendar (placeholder)
      googleCreateEvent() {
        console.log("Adding event to Google Calendar...");
        console.log("Selected Event:", this.selectedEvent);
  
        // Simulate success
        const successModalInstance = new bootstrap.Modal(
          document.getElementById("successModal2")
        );
        successModalInstance.show();
      },
    },
  }).mount("#home");


const buyTicketApp = Vue.createApp({
    data() {
        return { tickets: [], message: "" };
    },
    async created() {
        this.tickets = await fetchAvailableTickets();
    },
    methods: {
        async buyTicket(ticketID) {
            this.message = await buyTicketAPI(ticketID);
        }
    }
}).mount("#buyTicket");

const resaleApp = Vue.createApp({
    data() {
        return { ticketID: "", resaleTicketID: "", price: "", message: "" };
    },
    methods: {
        async buyResaleTicket() {
            this.message = await buyResaleAPI(this.ticketID);
        },
        async resellTicket() {
            this.message = await resellTicketAPI(this.resaleTicketID, this.price);
        }
    }
}).mount("#resale");

const checkinApp = Vue.createApp({
    data() {
        return { ticketID: "", message: "" };
    },
    methods: {
        async checkIn() {
            this.message = await checkInAPI(this.ticketID);
        }
    }
}).mount("#checkin");


