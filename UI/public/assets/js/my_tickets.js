const myTicketsApp = Vue.createApp({
    data() {
      return {
        confirmedTickets: [],
        waitlistedEvents: [],
        loading: true
      };
    },
    created() {
      const sessionUser = sessionStorage.getItem("user");
  
      if (!sessionUser) {
        alert("You are not logged in.");
        window.location.href = "login.html";
        return;
      }
  
      const user = JSON.parse(sessionUser);
      const ownerID = user.email; // ✅ Use email as the ownerID
      
      const sessionId = new URLSearchParams(window.location.search).get("session_id");
  if (sessionId) {
    // Call your Flask backend to verify and possibly store the booking
    fetch(`http://localhost:5007/verify-payment?session_id=${sessionId}`)
      .then(res => res.json())
      .then(data => {
        if (data.payment_intent_id) {
          alert("Payment Verified!")
          console.log(" Verified Payment:", data);

        } else {
          console.warn("Payment session verification failed.");
        }
      })
      .catch(err => {
        console.error("Error verifying payment:", err);
      });
  }
      this.fetchTickets(ownerID);
    },
    methods: {
      async fetchTickets(ownerID) {
        try {
          const [confirmedRes, waitlistRes] = await Promise.all([
            fetch(`http://localhost:5004/tickets/${ownerID}`),
            fetch(`http://localhost:5003/waitlist/user/${ownerID}`)
          ]);
  
          const confirmedData = await confirmedRes.json();
          const waitlistData = await waitlistRes.json();
  
          if (confirmedData.code === 200) {
            this.confirmedTickets = confirmedData.data;
          }
  
          if (waitlistData.code === 200) {
            this.waitlistedEvents = waitlistData.data.waitlist;
          }
        } catch (error) {
          console.error("Error loading tickets:", error);
          alert("Something went wrong while loading tickets.");
        } finally {
          this.loading = false;
        }
      },
      formatDateTime(datetimeStr) {
        const date = new Date(datetimeStr);
        return date.toLocaleString("en-SG", {
          dateStyle: "medium",
          timeStyle: "short"
        });
      }
    }
  }).mount("#myTicketsApp");
  