import json
import time
import csv
import os

from strategies import (
    sliding_window,
    observation_masking,
    recursive_summarization,
    zone_based_pruning
)



# ==========================================
# Load Test Cases
# ==========================================

def load_test_cases():

    with open(
        "test_cases.json",
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)





# ==========================================
# Token Estimation
# ==========================================

def calculate_tokens(messages):

    text = ""

    for msg in messages:

        text += msg["content"] + " "


    # Simple token approximation

    return len(text.split())





# ==========================================
# Accuracy Evaluation
# ==========================================

def calculate_accuracy(
        response,
        expected
):

    response = response.lower()

    expected = expected.lower()


    if expected in response:

        return 1

    return 0





# ==========================================
# Simulated Agent Response
# ==========================================

def simulate_agent(context, question):

    """
    Simulation instead of calling Groq.
    The evaluation focuses on context strategies.
    """

    full_text = " ".join(

        msg["content"]

        for msg in context

    ).lower()



    if "open tickets" in question.lower():

        if "7" in full_text:

            return "There are 7 open tickets."



    if "team" in question.lower():

        if "development" in full_text:

            return "Development team is responsible."



    return "Information unavailable."





# ==========================================
# Evaluation Runner
# ==========================================

def evaluate_strategy(
        name,
        strategy,
        test_cases
):


    total_accuracy = 0

    total_tokens = 0

    total_latency = 0



    for case in test_cases:


        messages = case["messages"]

        question = case["question"]

        expected = case["expected"]



        start = time.time()



        processed_context = strategy(
            messages
        )



        response = simulate_agent(

            processed_context,

            question

        )



        end = time.time()



        accuracy = calculate_accuracy(

            response,

            expected

        )



        tokens = calculate_tokens(

            processed_context

        )



        latency = end - start



        total_accuracy += accuracy

        total_tokens += tokens

        total_latency += latency




    count = len(test_cases)



    return {

        "Strategy": name,

        "Accuracy":

            round(
                (total_accuracy / count) * 100,
                2
            ),


        "Average Tokens":

            round(
                total_tokens / count,
                2
            ),


        "Average Latency":

            round(
                total_latency / count,
                4
            )

    }






# ==========================================
# Main
# ==========================================

def main():

    test_cases = load_test_cases()



    strategies = {


        "Sliding Window":

            sliding_window,


        "Observation Masking":

            observation_masking,


        "Recursive Summarization":

            recursive_summarization,


        "Zone Based Pruning":

            zone_based_pruning

    }



    results = []



    for name, strategy in strategies.items():


        print(
            f"Evaluating {name}..."
        )


        result = evaluate_strategy(

            name,

            strategy,

            test_cases

        )


        results.append(result)





    with open(

        "results.csv",

        "w",

        newline="",

        encoding="utf-8"

    ) as f:


        writer = csv.DictWriter(

            f,

            fieldnames=results[0].keys()

        )


        writer.writeheader()

        writer.writerows(results)




    print(
        "\nEvaluation Completed!"
    )

    print(
        "Results saved in results.csv"
    )





if __name__ == "__main__":

    main()