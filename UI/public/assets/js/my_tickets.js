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
  