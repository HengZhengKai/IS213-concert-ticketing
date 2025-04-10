const myTicketsApp = Vue.createApp({
  data() {
    return {
      confirmedTickets: [],
      waitlistedEvents: [],
      loading: true,
      sessionId: new URLSearchParams(window.location.search).get("session_id"), // get sessionId from URL
      userID: JSON.parse(sessionStorage.getItem("user"))?.userID // get userID from sessionStorage
    };
  },
  created() {
    if (!this.userID) {
      alert("You are not logged in.");
      window.location.href = "login.html";
      return;
    }



    this.buyTicket();
    this.fetchTickets();
  },
  methods: {
    async fetchTickets() {
      try {
        // Fetch tickets and waitlisted events for the user
        const [ticketRes, waitlistRes] = await Promise.all([
          fetch(`http://localhost:8000/tickets/${this.userID}`),
          fetch(`http://localhost:8000/waitlist/user/${this.userID}`)
        ]);

        const ticketData = await ticketRes.json();
        const waitlistData = await waitlistRes.json();
        console.log("works")

        if (ticketData.code === 200) {
          this.confirmedTickets = ticketData.data.tickets;
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
    async buyTicket() {
      const urlParams = new URLSearchParams(window.location.search);  // ✅ Define this!

            const sessionId = urlParams.get('session_id');
            console.log("sesh id works")
        
            if (!sessionId) {
                showError('Missing required parameters');
                return;
            }
            console.log("works2")
        if (!this.sessionId) {
          alert("Session ID is missing!");
          return;
        }
      
        // Log sessionId for debugging
        console.log("Session ID:", this.sessionId);

    
        // Verify payment
        const verifyRes = await fetch(`http://localhost:8000/verify-payment?session_id=${this.sessionId}`);
        const verifyData = await verifyRes.json();
    
        // Log the response from the verify-payment API
        console.log("Payment Verification Response:", verifyData);
    
        if (!verifyRes.ok || !verifyData.payment_intent_id) {
          throw new Error(verifyData.error || 'Could not verify payment');
        }
    
        const paymentIntentID = verifyData.payment_intent_id;
    
        // Define the seats to be added to the payload
        const selectedSeatsData = JSON.parse(sessionStorage.getItem('selectedSeats'));
        if (!selectedSeatsData || !selectedSeatsData.length) {
          throw new Error('No seats selected for booking');
        }
      
        // Use the selected seats for the payload
        const seats = selectedSeatsData.map(seat => ({
          seatNo: seat.seatNo,
          seatCategory: seat.category,
          price: seat.price,
          paymentID: paymentIntentID
        }));

        console.log(selectedSeatsData[0].eventDateTime)

        // Log the retrieved seat details
        console.log("Retrieved Seats:", selectedSeatsData);
        selectedEventName = selectedSeatsData[0].eventName
        selectedEventID = selectedSeatsData[0].eventID
        selectedEventDateTime = selectedSeatsData[0].eventDateTime.replace(' ', '+')


        // Log the payload to be sent
        console.log("Payload to Buy Ticket:", {
          userID: this.userID,
          eventName: selectedEventName,
          eventID: selectedEventID,
          eventDateTime: selectedEventDateTime,
          seats: seats
        });
    
        const payload = {
          userID: this.userID,
          eventName: selectedEventName,
          eventID: selectedEventID,
          eventDateTime: selectedEventDateTime,
          seats: seats
        };
    
        for(seat of seats){
          console.log(seat.seatNo)
        }

        // Make the API call to buy the ticket

        const response = await fetch(`http://localhost:8000/buyticket`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload)
        });
    
        // Check if the response is not OK
        if (!response.ok) {
          const errorData = await response.json();
          console.error("Error Response:", errorData);
          throw new Error(`Error: ${response.status} - ${errorData.message}`);
        }
    
        const responseData = await response.json();
        console.log("Buy Ticket Response:", responseData);
    
        if (response.ok) {
          this.confirmedTickets.push(...responseData.data);
          alert("Ticket purchased successfully!");
        } else {
          console.error("Error purchasing ticket:", responseData.message);
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