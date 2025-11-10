from finagents import MarketDataAgent
from finagents import TechnicalAnalysisAgent
from finagents import FundamentalAnalysisAgent
from finagents import SentimentAnalysisAgent
from finagents import RiskManagementAgent
from finagents import PortfolioManagementAgent
from finagents import TradeExecutionAgent
import time
import asyncio
from agents import Agent, Runner, handoff
from utils import TradeLogger
import json

class PortfolioTradingManager:

    def __init__(self, customer_id:str, stockname:str):
       
        self.customer_id = customer_id
        self.stockname = stockname
        self.query = "Analyse a stock with stockname/ticker-symbol as "+stockname+" for a customer whose customer_id is " +customer_id+" ."

    """
    This class Orchestrates the entire agentic-ai based process for a trading recommendation- 
    (1) MarketDataAgent gets the price history
    (2) TechnicalAnalysisAgent, FundamentalAnalysisAgent, SentimentAnalysisAgent run in parallel
    (3) RiskManagerAgent evaluates recommendation from the prior agents against customer's risk tolerance
    (4) PortfolioManagerAgent evaluates the signals and risk evaluation against customer's investment
        portofio, goals & constraints to provide final recommendation.
    """
    async def run_agent(self, agent, query=None):
        #result = await Runner.run(agent, input=self.query)
        if query is not None:
            result = await agent.run(query)  
        else:
            result = await agent.run(self.query)
        
        return result
    async def orchestrate_workflow(self):

        return
    
    async def should_enable_handoff(self, ctx):
        print('should_enable_handoff called with context:', ctx)
        return True
    
    async def log_handoff(self, ctx):
        print('handoff to Tech Analysis Agent happened', ctx)
        
    async def run_agents(self):
        
        """
            This function 'run_agents' follows the typical portfolio trading procedure, in the order of 
            (1) stock analysis, 
            (2) risk evaluation, 
            (3) customer portfolio analysis.
            First, it creates a MetaAgent to orchestrate a sub-process of MarketDataAgent gathering market price
            followed by a group of agents (tech, fundamental, sentiment) running in parallel.
        """
        PROMPT = (
            "You are a meta agent. Given a "+self.stockname+", consolidate buy/sell signals and rationale from:"

            "TechnicalAnalysisAgent (LSTM breakout prediction, Technical Indicators such as RSI, MACD, EMA, etc.)"
            "FundamentalAnalysisAgent (PE, PEG, growth, macro indicators)"
            "SentimentAnalysisAgent (news sentiment, bullish ratio, trend)"
            "Combine all inputs into a detailed summary and recommend a final buy or sell with reasoning."
        )
        
        meta_agent = Agent(
            name="MetaAgent",
            instructions=PROMPT
        )
        agent_a = MarketDataAgent()
        agent_b = TechnicalAnalysisAgent()
        agent_c = FundamentalAnalysisAgent()
        agent_d = SentimentAnalysisAgent()
        
        # The following block shows how to handoff from one agent to another. 
        # But in this case we are not using it as the handoff is not guaranteed.    
        # handoff from agent a to agent b for tech analysis
        
        # agent_a.agent.handoffs.append(
        #         handoff(
        #             agent=agent_b.agent, is_enabled=self.should_enable_handoff, on_handoff=self.log_handoff
        #             )
        #         )
        # agent_a.agent.instructions += " After you are done, you must always handoff to TechnicalAnalysisAgent for technical indicators calculations such as Bollinger Bands, MACD etc."
        # agent_a.agent.instructions +=" Pass input to TechnicalAnalysisAgent as "+self.query+" ."
        
        # Run MarketDataAgent first to get the price history
        market_data_agent_output = await self.run_agent(agent_a, self.query)
        market_data_agent_output_text = market_data_agent_output.final_output
        market_data_summary = f"### {market_data_agent_output.last_agent.name}\n{market_data_agent_output_text}"
        # Now run the tech, fundamental & sentiment analysis agents in parallel
        parallel_agents = [
            agent_b,
            agent_c,
            agent_d
        ]
        #asyncio.get_event_loop().run_until_complete(run_agents(parallel_agents, user_input,customer_id))
        
        responses = await asyncio.gather(
            *(self.run_agent(agent) for agent in parallel_agents)
        )

        labeled_summaries = [
            f"### {resp.last_agent.name}\n{resp.final_output}"
            for resp in responses
        ]
        labeled_summaries.insert(0, market_data_summary)
        """
        After parallel runs of tech, fundamental & sentiment analysis, 
        consolidate & summarize the outputs from them through a meta agent,
        then run the risk and portfolio analysis in sequence.
        Gather the outputs in a list to be later published as report.
        """

        output = []
        
        # MetaAgent to consolidate the outputs of stock analysis. 
        # This is not a core agent and has been created to show how parallelism can be achieved.
        collected_summaries = "\n".join(labeled_summaries)
        final_summary_meta_output = await Runner.run(meta_agent, input=collected_summaries)
        final_summary_meta = final_summary_meta_output.final_output
        
        output.append(final_summary_meta)

        #Get the risk manager in action with the meta agent output (buy/sell recommendation)
        agent_e = RiskManagementAgent()
        final_summary_meta += ". You should know that you are risk analysing a stock with ticker symbol as "+self.stockname+" for a customer whose customer_id is "+self.customer_id+" ."

        final_summary_risk_output = await self.run_agent(agent_e, final_summary_meta)
        #print('final_summary_risk_output: ',final_summary_risk_output)
        final_summary_risk = final_summary_risk_output.final_output
        output.append(final_summary_risk)

        #Get the portfolio manager in action with the clearance from risk manager on buy/sell recommendation
        agent_f = PortfolioManagementAgent()
        final_summary_risk += ". You should know that you are analysing a stock with ticker symbol as "+self.stockname+" for a customer whose customer_id is "+self.customer_id+" ."
        final_summary_portfolio_output = await self.run_agent(agent_f, final_summary_risk)
        final_summary_portfolio = final_summary_portfolio_output.final_output
        
        output.append(final_summary_portfolio)
        
        # Let the trade execution agent extract the recommendation from the portfolio management agent's output 
        # and execute it.
        start_index = final_summary_portfolio.find("Executive Summary")
        end_index = final_summary_portfolio.find("Summary for You")
        if end_index == -1:
            end_index = len(final_summary_portfolio)
        text_to_analyze = final_summary_portfolio[start_index:end_index]
        
        # Set up TradeExecutionAgent to parse the exec summary and log the trade if action is BUY or SELL
        agent_g = TradeExecutionAgent()
        query = "You are a text parser agent who will extract trade signal from the following - "+text_to_analyze
        trade_execution_details = await self.run_agent(agent_g, query)
        trade_execution_json = trade_execution_details.final_output
        print('trade_execution_json:', trade_execution_json)
        output_json = json.loads(trade_execution_json)
        
        # Log the trade if action is BUY or SELL
        if output_json.get("action", "HOLD") != "HOLD":
            trade_logger = TradeLogger()
            trade_logger.log_trade(output_json, self.stockname)
        
        #print('\n')
        text = "Lets us look at the output of MetaAgent, RiskManagementAgent, PortfolioManagementAgent, followed by Exec Summary."
        for word in text.split(sep=' '):
            print(word, end=' ', flush=True)
            time.sleep(0.1)
        print('\n')
        print('Look into the output folder for analysis report')
        #print(*output, sep='\n')

        return output
