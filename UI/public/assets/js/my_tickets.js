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
        const ownerID = user.userID;
      
        const sessionId = new URLSearchParams(window.location.search).get("session_id");
        if (sessionId) {
          fetch(`http://localhost:8000/verify-payment?session_id=${sessionId}`)
            .then(res => res.json())
            .then(data => {
              if (data.payment_intent_id) {
                alert("Payment Verified!");
                console.log("Verified Payment:", data);
              } else {
                console.warn("Payment session verification failed.");
              }
            })
            .catch(err => {
              console.error("Error verifying payment:", err);
            });
        }
      
        // ✅ Call with both ticket and waitlist userIDs
        this.fetchTickets(user.userID, user.userID);
      
      
    },
    methods: {
      async fetchTickets(ownerID, waitlistUserID) {
        try {
          const [ticketRes, waitlistRes] = await Promise.all([
            fetch(`http://localhost:8000/tickets/${ownerID}`),
            fetch(`http://localhost:8000/waitlist/user/${waitlistUserID}`)
          ]);
      
          const ticketData = await ticketRes.json();
          const waitlistData = await waitlistRes.json();
      
          if (ticketData.code === 200) {
            const allTickets = ticketData.data.tickets;
            console.log("✅ All Tickets:", allTickets); // Debug output
      
            this.confirmedTickets = allTickets.map(ticket => ({
              ticketID: ticket.ticketID,
              eventName: ticket.eventName,
              eventDateTime: ticket.eventDateTime,
              seatNo: ticket.seatNo,
              seatCategory: ticket.seatCategory,
              status: ticket.status,
              isCheckedIn: ticket.isCheckedIn
            }));
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
  